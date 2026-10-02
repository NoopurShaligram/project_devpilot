from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from forge_advisor.config import settings
from forge_advisor.models.domain import TaskAnalysis, TaskCategory


SYSTEM_PROMPT = """
You are Forge's Task Analyzer.

Your job is ONLY to semantically understand a software-development request.
Do not recommend an interface, workflow, tools, permissions, or risk level.
A separate deterministic policy engine will make those decisions.

Classify the request conservatively.
Distinguish:
- explanation: understanding/conceptual help, no repo modification needed
- debugging: finding/fixing an existing problem
- small_edit: localized code/config change
- feature: adding functionality
- refactor: restructuring existing code without primarily changing behavior
- repository_operation: Git/file/repository management
- data_operation: database/data changes or data-handling operations
- production_operation: deployment/release/production changes
- planning: design/requirements/planning without implementation

Use evidence from the request. Do not invent repository details.
""".strip()


prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "Developer task:\n{task}"),
    ]
)


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _heuristic_analysis(task: str) -> TaskAnalysis:
    """Deterministic fallback so Forge can run without an LLM key."""
    t = task.lower().strip()

    explanation = _contains_any(
        t,
        ("explain", "what is", "how does", "why does", "difference between", "teach me"),
    )
    debugging = _contains_any(
        t,
        ("debug", "debugging", "bug", "error", "exception", "stack trace", "failing", "fails", "fix"),
    )
    refactor = _contains_any(t, ("refactor", "restructure", "clean up", "simplify", "move logic"))
    production = _contains_any(
        t,
        ("deploy", "production", "release", "rollout", "publish to prod", "rollback"),
    )
    data_operation = _contains_any(
        t,
        ("database", "db", "migration", "migrate", "drop table", "delete users", "customer data", "sql"),
    )
    repository_operation = _contains_any(
        t,
        ("git", "branch", "commit", "pull request", "merge", "repo", "repository", "file"),
    )
    terminal = _contains_any(
        t,
        ("run", "execute", "pytest", "test", "build", "npm", "yarn", "pnpm", "docker", "install", "lint", "compile"),
    )
    external = _contains_any(
        t,
        ("github", "jira", "slack", "database", "postgres", "mysql", "email", "send an email", "api"),
    )
    sensitive = _contains_any(
        t,
        ("production", "customer data", "user data", "credentials", "secret", "token", "password", "private key"),
    )
    destructive = production or _contains_any(
        t,
        ("delete", "drop ", "truncate", "overwrite", "send email", "send emails", "remove all"),
    )

    repo = (
        repository_operation
        or _contains_any(
            t,
            ("code", "function", "class", "endpoint", "backend", "frontend", "fastapi", "django", "react", "implement", "add "),
        )
    )

    if explanation and not debugging:
        category = TaskCategory.explanation
    elif production:
        category = TaskCategory.production_operation
    elif data_operation:
        category = TaskCategory.data_operation
    elif refactor:
        category = TaskCategory.refactor
    elif debugging:
        category = TaskCategory.debugging
    elif _contains_any(t, ("add ", "implement", "build", "create", "introduce")):
        category = TaskCategory.feature
    elif repository_operation:
        category = TaskCategory.repository_operation
    elif repo:
        category = TaskCategory.small_edit
    else:
        category = TaskCategory.planning

    likely_files = "unknown"
    if category in {TaskCategory.feature, TaskCategory.refactor}:
        likely_files = "multiple"
    elif category in {TaskCategory.debugging, TaskCategory.small_edit}:
        likely_files = "single"
    elif category in {TaskCategory.production_operation, TaskCategory.data_operation}:
        likely_files = "unknown"

    read_only = not (repo or terminal or destructive)

    reasons = []
    if repo:
        reasons.append("Repository/code context is relevant")
    if terminal:
        reasons.append("Command or test execution is implied")
    if external:
        reasons.append("An external system or integration may be involved")
    if sensitive:
        reasons.append("Sensitive information or state may be involved")
    if destructive:
        reasons.append("The request may create an irreversible side effect")
    if not reasons:
        reasons.append("The request can be interpreted without repository execution")

    return TaskAnalysis(
        category=category,
        summary=task.strip(),
        requires_repository_context=repo,
        requires_terminal=terminal,
        requires_external_tools=external,
        likely_files_affected=likely_files,
        requires_execution=terminal or production or data_operation,
        touches_sensitive_data=sensitive,
        destructive_or_irreversible=destructive,
        likely_needs_human_review=production or data_operation or destructive,
        can_be_read_only=read_only,
        rationale=reasons[:5],
    )


def analyze_task(task: str) -> TaskAnalysis:
    if not settings.openai_api_key or not settings.llm_model:
        return _heuristic_analysis(task)

    model = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )
    structured_model = model.with_structured_output(TaskAnalysis)
    result = (prompt | structured_model).invoke({"task": task})

    # Defensive validation at the boundary.
    return TaskAnalysis.model_validate(result)
