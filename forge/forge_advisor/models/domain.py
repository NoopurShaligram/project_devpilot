from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TaskCategory(str, Enum):
    explanation = "explanation"
    debugging = "debugging"
    small_edit = "small_edit"
    feature = "feature"
    refactor = "refactor"
    repository_operation = "repository_operation"
    data_operation = "data_operation"
    production_operation = "production_operation"
    planning = "planning"


class Interface(str, Enum):
    chat = "chat"
    ide_agent = "ide_agent"
    coding_agent = "coding_agent"


class Risk(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TaskAnalysis(BaseModel):
    category: TaskCategory
    requires_repository_context: bool
    requires_terminal: bool
    requires_external_tools: bool
    likely_files_affected: str = Field(
        description="single, few, multiple, or unknown"
    )
    requires_execution: bool
    touches_sensitive_data: bool
    destructive_or_irreversible: bool = False
    likely_needs_human_review: bool = False
    can_be_read_only: bool
    rationale: list[str] = Field(min_length=1)


class AdvisorResponse(BaseModel):
    task: str
    analysis: TaskAnalysis
    recommended_interface: Interface
    recommended_workflow: list[str]
    risk: Risk
    requires_human_approval: bool
    approval_points: list[str]
    required_capabilities: list[str]
    rationale: list[str]


class PlanStep(BaseModel):
    id: int
    name: str
    objective: str
    responsible_role: Literal[
        "planner",
        "architect",
        "implementer",
        "tester",
        "reviewer",
        "human",
    ]
    expected_output: str


class ImplementationPlan(BaseModel):
    summary: str
    assumptions: list[str] = Field(default_factory=list)
    files_to_inspect: list[str] = Field(default_factory=list)
    files_likely_to_change: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)
    rollback_strategy: str
    steps: list[PlanStep] = Field(min_length=1)


class ApprovalDecision(BaseModel):
    approved: bool
    note: str = ""


class FinalDecision(str, Enum):
    approved = "approved"
    request_changes = "request_changes"
    rejected = "rejected"


class FinalReviewDecision(BaseModel):
    decision: FinalDecision
    note: str = ""


class TestResult(BaseModel):
    status: Literal["passed", "failed", "skipped", "error"]
    command: str
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0


class ReviewIssue(BaseModel):
    severity: Literal["low", "medium", "high", "critical"]
    file: str | None = None
    issue: str
    recommendation: str


class ReviewReport(BaseModel):
    decision: Literal["approve", "changes_requested"]
    summary: str
    architecture_compliant: bool
    tests_adequate: bool
    issues: list[ReviewIssue] = Field(default_factory=list)


class UsageTotals(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model_calls: int = 0
    tool_calls: int = 0


class ImplementationResult(BaseModel):
    status: Literal["completed", "skipped", "failed"]
    summary: str
    agent_output: str = ""
    changed_files: list[str] = Field(default_factory=list)
    usage: UsageTotals = Field(default_factory=UsageTotals)
