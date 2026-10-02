from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from forge_advisor.config import settings
from forge_advisor.models.domain import TaskAnalysis


SYSTEM = """
You are the semantic task analyzer for Forge, an AI-assisted software engineering advisor.
Analyze the developer's task. Do not recommend tools or permissions yet.
Return only the requested structured fields.
Be conservative when inferring destructive or sensitive operations.
"""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM),
        ("human", "Developer task:\n{task}"),
    ]
)


def _heuristic_analysis(task: str) -> TaskAnalysis:
    t = task.lower()
    requires_repo = any(x in t for x in ["code", "repo", "repository", "file", "function", "api", "backend", "frontend", "refactor", "implement", "fix", "test"])
    terminal = any(x in t for x in ["run", "execute", "build", "test", "pytest", "npm", "docker", "install"])
    external = any(x in t for x in ["github", "jira", "slack", "database", "postgres", "email", "api"])
    sensitive = any(x in t for x in ["production", "deploy", "delete", "drop ", "customer data", "user data", "credentials", "secret", "send email"])

    if any(x in t for x in ["explain", "what is", "why does"]):
        category = "explanation"
    elif any(x in t for x in ["debug", "bug", "fix"]):
        category = "debugging"
    elif any(x in t for x in ["refactor", "restructure"]):
        category = "refactor"
    elif any(x in t for x in ["deploy", "production"]):
        category = "production_operation"
    elif any(x in t for x in ["database", "migration", "drop table", "delete users"]):
        category = "data_operation"
    elif any(x in t for x in ["add", "implement", "build", "create"]):
        category = "feature"
    else:
        category = "planning"

    return TaskAnalysis(
        category=category,
        requires_repository_context=requires_repo,
        requires_terminal=terminal,
        requires_external_tools=external,
        likely_files_affected="multiple" if any(x in t for x in ["refactor", "authentication", "oauth", "feature", "implement"]) else "unknown",
        requires_execution=terminal,
        touches_sensitive_data=sensitive,
        can_be_read_only=not requires_repo and not terminal and not sensitive,
        rationale="Heuristic fallback used because no LLM configuration is available.",
    )


def analyze_task(task: str) -> TaskAnalysis:
    if not settings.openai_api_key or not settings.llm_model:
        return _heuristic_analysis(task)

    model = ChatOpenAI(model=settings.llm_model, api_key=settings.openai_api_key, temperature=0)
    structured = model.with_structured_output(TaskAnalysis)
    return (prompt | structured).invoke({"task": task})
