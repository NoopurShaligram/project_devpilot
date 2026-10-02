from forge_advisor.models.domain import AdvisorResponse, Interface, Risk, TaskAnalysis, TaskCategory


def determine_risk(analysis: TaskAnalysis) -> Risk:
    """Policy layer: deterministic, auditable, independent of the LLM."""
    if analysis.category == TaskCategory.production_operation:
        return Risk.critical

    if (
        analysis.destructive_or_irreversible
        or analysis.touches_sensitive_data
        or analysis.category == TaskCategory.data_operation
    ):
        return Risk.high

    if analysis.requires_execution or analysis.requires_repository_context:
        return Risk.medium

    return Risk.low


def recommend_interface(analysis: TaskAnalysis) -> tuple[Interface, str]:
    if analysis.category == TaskCategory.explanation and analysis.can_be_read_only:
        return Interface.chat, "The task is primarily explanatory and does not need repository execution."

    if analysis.requires_repository_context and analysis.requires_execution:
        return Interface.coding_agent, "The task needs repository context plus command/test execution across the development workflow."

    if analysis.requires_repository_context:
        return Interface.ide_agent, "The task benefits from live code context but does not clearly require a full terminal-driven workflow."

    return Interface.chat, "The task can be handled primarily through reasoning and conversation."


def build_workflow(analysis: TaskAnalysis, risk: Risk) -> list[str]:
    if analysis.category == TaskCategory.explanation:
        return ["Ask → Explain"]

    if analysis.category == TaskCategory.planning:
        return ["Clarify requirements", "Produce plan", "Review plan"]

    if analysis.category == TaskCategory.debugging:
        steps = ["Inspect relevant context", "Reproduce or reason about failure", "Propose fix"]
        if analysis.requires_execution:
            steps += ["Run tests/checks", "Review diff"]
        return steps

    if analysis.category == TaskCategory.production_operation:
        return [
            "Inspect deployment context",
            "Produce execution plan",
            "Human approval",
            "Execute deployment",
            "Verify production state",
            "Human approval for rollback/escalation if needed",
        ]

    if analysis.category == TaskCategory.data_operation:
        return [
            "Inspect schema/data context",
            "Plan data operation",
            "Validate impact",
            "Human approval",
            "Execute",
            "Verify result",
        ]

    if analysis.category == TaskCategory.refactor:
        return ["Inspect repository", "Plan refactor", "Implement", "Run tests", "Review diff"]

    if analysis.requires_repository_context and analysis.requires_execution:
        return ["Inspect repository", "Plan", "Implement", "Run tests", "Review diff"]

    if analysis.requires_repository_context:
        return ["Inspect context", "Propose change", "Review diff"]

    return ["Clarify task", "Propose solution", "Review result"]


def build_approval_points(analysis: TaskAnalysis, risk: Risk) -> list[str]:
    points: list[str] = []

    if risk == Risk.critical:
        points.append("Approve before any production-affecting action")
    elif risk == Risk.high:
        points.append("Approve before any destructive, sensitive, or data-affecting action")

    if analysis.requires_repository_context and analysis.requires_execution:
        points.append("Review final diff and test results before merge")

    if analysis.requires_external_tools:
        points.append("Confirm external-system side effects before execution")

    return points


def build_capabilities(analysis: TaskAnalysis) -> list[str]:
    capabilities: list[str] = []

    if analysis.requires_repository_context:
        capabilities.append("repository/filesystem")
    if analysis.requires_terminal:
        capabilities.append("terminal/test runner")
    if analysis.requires_external_tools:
        capabilities.append("external integrations")

    return capabilities


def make_response(task: str, analysis: TaskAnalysis) -> AdvisorResponse:
    risk = determine_risk(analysis)
    interface, interface_reason = recommend_interface(analysis)
    workflow = build_workflow(analysis, risk)
    approval_points = build_approval_points(analysis, risk)
    capabilities = build_capabilities(analysis)

    rationale = list(analysis.rationale)
    rationale.append(f"Deterministic policy classified the task as {risk.value} risk.")
    if approval_points:
        rationale.append("At least one approval gate is required because the workflow can change code or external state.")

    return AdvisorResponse(
        task=task,
        analysis=analysis,
        recommended_interface=interface,
        interface_reason=interface_reason,
        recommended_workflow=workflow,
        risk=risk,
        requires_human_approval=bool(approval_points),
        approval_points=approval_points,
        required_capabilities=capabilities,
        rationale=rationale,
    )
