from pathlib import Path

from langgraph.types import Command

from forge_advisor.agents.planner import generate_plan
from forge_advisor.graph.workflow import build_graph
from forge_advisor.models.domain import AdvisorResponse, Risk, TaskAnalysis, TaskCategory
from forge_advisor.services.project import load_project_instructions, safe_path


def _analysis(category=TaskCategory.feature):
    return TaskAnalysis(
        category=category,
        requires_repository_context=True,
        requires_terminal=True,
        requires_external_tools=False,
        likely_files_affected="multiple",
        requires_execution=True,
        touches_sensitive_data=False,
        destructive_or_irreversible=False,
        likely_needs_human_review=True,
        can_be_read_only=False,
        rationale=["Repository implementation task"],
    )


def _advisor(task: str, analysis: TaskAnalysis):
    return AdvisorResponse(
        task=task,
        analysis=analysis,
        recommended_interface="coding_agent",
        recommended_workflow=["Plan", "Approve", "Implement", "Test", "Review"],
        risk=Risk.medium,
        requires_human_approval=True,
        approval_points=["Review final diff before merge"],
        required_capabilities=["repository/filesystem", "terminal/test runner"],
        rationale=["Repository and execution are required."],
    )


def test_safe_path_blocks_escape(tmp_path: Path):
    safe = safe_path(str(tmp_path), "src/main.py")
    assert safe.parent == tmp_path / "src"

    try:
        safe_path(str(tmp_path), "../outside.txt")
    except ValueError:
        pass
    else:
        raise AssertionError("Path traversal should be rejected")


def test_project_instructions_are_loaded(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("Use typed functions.", encoding="utf-8")
    loaded = load_project_instructions(str(tmp_path))
    assert "Use typed functions." in loaded


def test_planner_has_offline_fallback(tmp_path: Path):
    analysis = _analysis()
    advisor = _advisor("Implement feature", analysis)
    plan, usage = generate_plan(
        task="Implement feature",
        analysis=analysis,
        advisor=advisor,
        instructions="Use tests.",
    )
    assert plan.steps
    assert plan.acceptance_criteria
    assert usage["model_calls"] in {0, 1}


def test_plan_approval_can_reject(tmp_path: Path):
    graph = build_graph()
    config = {"configurable": {"thread_id": "test-reject"}}

    result = graph.invoke(
        {
            "task": "Implement a feature and run tests",
            "project_root": str(tmp_path),
        },
        config,
    )

    assert result.get("__interrupt__")

    resumed = graph.invoke(
        Command(resume={"approved": False, "note": "Not ready"}),
        config,
    )

    assert resumed["status"] == "rejected"
