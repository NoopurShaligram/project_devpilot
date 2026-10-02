from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from forge_advisor.agents.implementer import implement_task
from forge_advisor.agents.planner import generate_plan
from forge_advisor.agents.reviewer import review_changes
from forge_advisor.config import settings
from forge_advisor.graph.state import DevState
from forge_advisor.models.domain import (
    AdvisorResponse,
    ApprovalDecision,
    FinalDecision,
    FinalReviewDecision,
    Interface,
    Risk,
    TaskCategory,
    UsageTotals,
    TestResult,
)
from forge_advisor.services.analyzer import analyze_task
from forge_advisor.services.diff import get_workspace_diff
from forge_advisor.services.project import (
    capture_text_snapshot,
    load_project_instructions,
)


def _policy(analysis) -> AdvisorResponse:
    if analysis.category == TaskCategory.explanation:
        interface = Interface.chat
        workflow = ["Ask → answer"]
    elif analysis.requires_repository_context and analysis.requires_execution:
        interface = Interface.coding_agent
        workflow = ["Inspect repository", "Plan", "Approve plan", "Implement", "Run tests", "Review diff"]
    elif analysis.requires_repository_context:
        interface = Interface.ide_agent
        workflow = ["Inspect context", "Propose change", "Review diff"]
    else:
        interface = Interface.chat
        workflow = ["Ask → answer"]

    if analysis.category == TaskCategory.production_operation:
        risk = Risk.critical
    elif (
        analysis.touches_sensitive_data
        or analysis.destructive_or_irreversible
        or analysis.category == TaskCategory.data_operation
    ):
        risk = Risk.high
    elif analysis.requires_execution or analysis.requires_repository_context:
        risk = Risk.medium
    else:
        risk = Risk.low

    approval_points = []
    if risk in {Risk.high, Risk.critical}:
        approval_points.append(
            "Approve before any destructive, sensitive, or production-affecting action"
        )
    if analysis.requires_repository_context and analysis.requires_execution:
        approval_points.append("Review the final diff and test results before merge")
    if analysis.requires_external_tools:
        approval_points.append("Confirm external-system side effects before execution")

    capabilities = []
    if analysis.requires_repository_context:
        capabilities.append("repository/filesystem")
    if analysis.requires_terminal:
        capabilities.append("terminal/test runner")
    if analysis.requires_external_tools:
        capabilities.append("external integrations")

    return AdvisorResponse(
        task="",
        analysis=analysis,
        recommended_interface=interface,
        recommended_workflow=workflow,
        risk=risk,
        requires_human_approval=bool(approval_points),
        approval_points=approval_points,
        required_capabilities=capabilities,
        rationale=analysis.rationale,
    )


def analyze_node(state: DevState) -> dict:
    analysis = analyze_task(state["task"])
    return {
        "analysis": analysis,
        "status": "analyzed",
        "fix_attempts": 0,
        "review_cycles": 0,
        "usage": UsageTotals(),
    }


def policy_node(state: DevState) -> dict:
    advisor = _policy(state["analysis"])
    advisor.task = state["task"]
    return {
        "advisor": advisor,
        "status": "planned_policy",
    }


def instructions_node(state: DevState) -> dict:
    return {
        "project_instructions": load_project_instructions(state["project_root"]),
        "status": "context_loaded",
    }


def plan_node(state: DevState) -> dict:
    plan, usage = generate_plan(
        task=state["task"],
        analysis=state["analysis"],
        advisor=state["advisor"],
        instructions=state.get("project_instructions", ""),
    )

    total = state.get("usage", UsageTotals())
    total.input_tokens += usage["input_tokens"]
    total.output_tokens += usage["output_tokens"]
    total.total_tokens += usage["total_tokens"]
    total.model_calls += usage["model_calls"]

    return {
        "plan": plan,
        "usage": total,
        "status": "awaiting_plan_approval",
    }


def plan_approval_node(state: DevState):
    decision = interrupt(
        {
            "type": "plan_approval",
            "message": "Forge has produced an execution plan. Approve it before the agent can modify the repository.",
            "task": state["task"],
            "risk": state["advisor"].risk.value,
            "plan": state["plan"].model_dump(mode="json"),
            "capabilities": state["advisor"].required_capabilities,
        },
        response_schema=ApprovalDecision,
    )

    return {
        "plan_approval": decision,
        "status": "plan_approved" if decision.approved else "plan_rejected",
    }


def route_after_plan_approval(state: DevState) -> str:
    return "capture_baseline" if state["plan_approval"].approved else "rejected"


def capture_baseline_node(state: DevState) -> dict:
    return {
        "baseline_snapshot": capture_text_snapshot(state["project_root"]),
        "status": "baseline_captured",
    }


def implement_node(state: DevState) -> dict:
    previous_tests = state.get("test_result")
    feedback_parts = []
    if previous_tests:
        feedback_parts.append(
            f"Previous test status: {previous_tests.status}\n"
            f"stdout:\n{previous_tests.stdout[-10000:]}\n"
            f"stderr:\n{previous_tests.stderr[-5000:]}"
        )

    previous_review = state.get("review")
    if previous_review:
        feedback_parts.append(
            "Previous reviewer findings:\n"
            + previous_review.model_dump_json(indent=2)
        )

    feedback = "\n\n".join(feedback_parts)

    result = implement_task(
        project_root=state["project_root"],
        task=state["task"],
        plan=state["plan"],
        project_instructions=state.get("project_instructions", ""),
        test_feedback=feedback,
    )

    total = state.get("usage", UsageTotals())
    impl_usage = result.usage
    total.input_tokens += impl_usage.input_tokens
    total.output_tokens += impl_usage.output_tokens
    total.total_tokens += impl_usage.total_tokens
    total.model_calls += impl_usage.model_calls
    total.tool_calls += impl_usage.tool_calls

    return {
        "implementation": result,
        "usage": total,
        "fix_attempts": state.get("fix_attempts", 0) + 1,
        "status": "implemented" if result.status == "completed" else result.status,
    }


def test_node(state: DevState) -> dict:
    import subprocess
    import sys
    import time

    start = time.perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=state["project_root"],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        result = TestResult(
            status="passed" if completed.returncode == 0 else "failed",
            command=f"{sys.executable} -m pytest -q",
            exit_code=completed.returncode,
            stdout=completed.stdout[-15000:],
            stderr=completed.stderr[-7000:],
            duration_seconds=round(time.perf_counter() - start, 3),
        )
    except subprocess.TimeoutExpired as exc:
        result = TestResult(
            status="error",
            command=f"{sys.executable} -m pytest -q",
            exit_code=None,
            stdout=(exc.stdout or "")[-15000:] if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "")[-7000:] if isinstance(exc.stderr, str) else "",
            duration_seconds=round(time.perf_counter() - start, 3),
        )
    except Exception as exc:
        result = TestResult(
            status="error",
            command=f"{sys.executable} -m pytest -q",
            stderr=str(exc),
            duration_seconds=round(time.perf_counter() - start, 3),
        )

    return {
        "test_result": result,
        "status": f"tests_{result.status}",
    }


def route_after_tests(state: DevState) -> str:
    result = state["test_result"]
    attempts = state.get("fix_attempts", 0)

    if result.status == "passed":
        return "review"

    if attempts < settings.max_fix_attempts:
        return "implement"

    return "review"


def review_node(state: DevState) -> dict:
    diff = get_workspace_diff(
        state["project_root"],
        state.get("baseline_snapshot", {}),
    )
    report, usage = review_changes(
        plan=state["plan"],
        instructions=state.get("project_instructions", ""),
        test_result=state["test_result"].model_dump_json(indent=2),
        diff=diff,
    )

    total = state.get("usage", UsageTotals())
    total.input_tokens += usage.input_tokens
    total.output_tokens += usage.output_tokens
    total.total_tokens += usage.total_tokens
    total.model_calls += usage.model_calls

    return {
        "diff": diff,
        "review": report,
        "usage": total,
        "status": "awaiting_final_review",
    }


def final_review_node(state: DevState):
    decision = interrupt(
        {
            "type": "final_review",
            "message": "Review the implementation, tests, and reviewer findings before Forge finishes the run.",
            "task": state["task"],
            "risk": state["advisor"].risk.value,
            "changed_files": state.get("implementation", {}).changed_files,
            "test_result": state["test_result"].model_dump(mode="json"),
            "review": state["review"].model_dump(mode="json"),
            "diff": state.get("diff", "")[-30000:],
        },
        response_schema=FinalReviewDecision,
    )

    return {
        "final_decision": decision,
        "status": decision.decision.value,
        "review_cycles": state.get("review_cycles", 0) + 1,
    }


def route_after_final_review(state: DevState) -> str:
    decision = state["final_decision"].decision
    cycles = state.get("review_cycles", 0)

    if decision == FinalDecision.approved:
        return "completed"
    if decision == FinalDecision.rejected:
        return "rejected"
    if cycles < settings.max_review_cycles:
        return "implement"
    return "rejected"


def completed_node(state: DevState) -> dict:
    return {"status": "completed"}


def rejected_node(state: DevState) -> dict:
    return {"status": "rejected"}


def advice_only_node(state: DevState) -> dict:
    return {"status": "advice_only"}


def route_after_policy(state: DevState) -> str:
    advisor = state["advisor"]
    if advisor.recommended_interface == Interface.chat:
        return "advice_only"
    return "load_instructions"


def build_graph(checkpointer=None):
    builder = StateGraph(DevState)

    builder.add_node("analyze_task", analyze_node)
    builder.add_node("apply_policy", policy_node)
    builder.add_node("load_instructions", instructions_node)
    builder.add_node("generate_plan", plan_node)
    builder.add_node("plan_approval", plan_approval_node)
    builder.add_node("capture_baseline", capture_baseline_node)
    builder.add_node("implement", implement_node)
    builder.add_node("test", test_node)
    builder.add_node("review", review_node)
    builder.add_node("final_review", final_review_node)
    builder.add_node("completed", completed_node)
    builder.add_node("rejected", rejected_node)
    builder.add_node("advice_only", advice_only_node)

    builder.add_edge(START, "analyze_task")
    builder.add_edge("analyze_task", "apply_policy")
    builder.add_conditional_edges(
        "apply_policy",
        route_after_policy,
        {
            "load_instructions": "load_instructions",
            "advice_only": "advice_only",
        },
    )
    builder.add_edge("advice_only", END)
    builder.add_edge("load_instructions", "generate_plan")
    builder.add_edge("generate_plan", "plan_approval")
    builder.add_conditional_edges(
        "plan_approval",
        route_after_plan_approval,
        {
            "capture_baseline": "capture_baseline",
            "rejected": "rejected",
        },
    )
    builder.add_edge("rejected", END)
    builder.add_edge("capture_baseline", "implement")
    builder.add_edge("implement", "test")
    builder.add_conditional_edges(
        "test",
        route_after_tests,
        {
            "implement": "implement",
            "review": "review",
        },
    )
    builder.add_edge("review", "final_review")
    builder.add_conditional_edges(
        "final_review",
        route_after_final_review,
        {
            "implement": "implement",
            "completed": "completed",
            "rejected": "rejected",
        },
    )
    builder.add_edge("completed", END)

    return builder.compile(
        checkpointer=checkpointer or InMemorySaver()
    )
