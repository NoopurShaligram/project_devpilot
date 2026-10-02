from typing import Any, TypedDict

from forge_advisor.models.domain import (
    AdvisorResponse,
    ApprovalDecision,
    FinalReviewDecision,
    ImplementationPlan,
    ImplementationResult,
    ReviewReport,
    TaskAnalysis,
    TestResult,
    UsageTotals,
)


class DevState(TypedDict, total=False):
    task: str
    project_root: str

    analysis: TaskAnalysis
    advisor: AdvisorResponse
    project_instructions: str
    plan: ImplementationPlan

    plan_approval: ApprovalDecision
    final_decision: FinalReviewDecision

    baseline_snapshot: dict[str, str]
    implementation: ImplementationResult
    test_result: TestResult
    diff: str
    review: ReviewReport

    fix_attempts: int
    review_cycles: int
    usage: UsageTotals
    status: str
    error: str
    artifacts: dict[str, Any]
