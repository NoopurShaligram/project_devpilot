from enum import Enum
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
    """Semantic interpretation produced by the LLM or heuristic fallback."""

    category: TaskCategory
    summary: str = Field(description="One sentence describing the actual developer task")

    requires_repository_context: bool = Field(
        description="Whether understanding files/code in the repository is important"
    )
    requires_terminal: bool = Field(
        description="Whether shell commands, builds, tests, package managers, or similar execution are useful"
    )
    requires_external_tools: bool = Field(
        description="Whether a service such as GitHub, Jira, Slack, a database, email, or another API is needed"
    )
    likely_files_affected: str = Field(
        description="single, few, multiple, or unknown"
    )
    requires_execution: bool = Field(
        description="Whether the workflow should execute code/commands rather than only explain or propose"
    )
    touches_sensitive_data: bool = Field(
        description="Whether the task involves credentials, secrets, personal/customer data, production data, or similar sensitive material"
    )
    destructive_or_irreversible: bool = Field(
        description="Whether the task may delete, overwrite, deploy, migrate, send, or otherwise cause an irreversible side effect"
    )
    likely_needs_human_review: bool = Field(
        description="Whether a human should probably review the result even before deterministic policy is applied"
    )
    can_be_read_only: bool = Field(
        description="Whether the task can be completed without changing files or external state"
    )
    rationale: list[str] = Field(
        min_length=1,
        description="2-5 concrete reasons supporting the classification"
    )


class AdvisorResponse(BaseModel):
    task: str
    analysis: TaskAnalysis

    recommended_interface: Interface
    interface_reason: str

    recommended_workflow: list[str] = Field(min_length=1)
    risk: Risk

    requires_human_approval: bool
    approval_points: list[str] = Field(default_factory=list)

    required_capabilities: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(min_length=1)
