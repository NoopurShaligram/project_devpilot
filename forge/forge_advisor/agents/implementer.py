from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from forge_advisor.config import settings
from forge_advisor.models.domain import ImplementationPlan, ImplementationResult, UsageTotals
from forge_advisor.services.project import capture_text_snapshot, iter_files
from forge_advisor.services.tools import build_implementation_tools

SYSTEM_PROMPT = """
You are Forge's implementation agent.

You operate inside ONE local repository supplied by Forge.

Rules:
1. Inspect before editing.
2. Follow the approved implementation plan exactly unless a test failure reveals a necessary correction.
3. Make the smallest practical change.
4. Do not commit, push, merge, deploy, install packages, or modify files outside the repository.
5. Never read or write secrets, credentials, private keys, or .env files.
6. Prefer updating tests when behavior changes.
7. Use the available tools instead of pretending to have inspected files.
8. Run pytest when appropriate.
9. Finish with a concise report of what changed and what remains.
""".strip()


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _usage_from_messages(messages) -> UsageTotals:
    totals = UsageTotals()
    totals.model_calls = 0
    totals.tool_calls = 0

    for message in messages:
        usage = getattr(message, "usage_metadata", None) or {}
        if usage:
            totals.input_tokens += int(usage.get("input_tokens", 0))
            totals.output_tokens += int(usage.get("output_tokens", 0))
            totals.total_tokens += int(usage.get("total_tokens", 0))
            totals.model_calls += 1

        tool_calls = getattr(message, "tool_calls", None) or []
        totals.tool_calls += len(tool_calls)

    return totals


def _changed_files(project_root: str, before: dict[str, str]) -> list[str]:
    root = __import__("pathlib").Path(project_root).resolve()
    after = {
        str(path.relative_to(root))
        for path in iter_files(project_root)
    }
    before_paths = set(before)
    changed = set()

    for rel in sorted(before_paths | after):
        target = root / rel
        old = before.get(rel)
        if target.exists() and target.is_file():
            try:
                new = target.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                new = None
        else:
            new = None
        if old != new:
            changed.add(rel)

    return sorted(changed)


def implement_task(
    project_root: str,
    task: str,
    plan: ImplementationPlan,
    project_instructions: str,
    test_feedback: str = "",
) -> ImplementationResult:
    before = capture_text_snapshot(project_root)

    if not settings.openai_api_key or not settings.llm_model:
        return ImplementationResult(
            status="skipped",
            summary="No LLM credentials configured; implementation was not executed.",
        )

    model = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )

    tools = build_implementation_tools(project_root)
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        name="forge_implementer",
    )

    prompt = f"""
DEVELOPER TASK:
{task}

APPROVED PLAN:
{plan.model_dump_json(indent=2)}

PROJECT INSTRUCTIONS:
{project_instructions or "No instruction files were found."}

PREVIOUS TEST FEEDBACK:
{test_feedback or "No previous test failure."}

Execute the plan in the repository. Use tools to inspect and modify files.
Do not perform external side effects.
""".strip()

    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config={"recursion_limit": settings.max_agent_recursion},
        )
    except Exception as exc:
        return ImplementationResult(
            status="failed",
            summary=f"Implementation agent failed: {exc}",
        )

    messages = result.get("messages", [])
    final_text = ""
    for message in reversed(messages):
        if getattr(message, "type", None) == "ai":
            final_text = _extract_text(getattr(message, "content", ""))
            break

    usage = _usage_from_messages(messages)
    changed = _changed_files(project_root, before)

    return ImplementationResult(
        status="completed",
        summary="Implementation agent completed its run.",
        agent_output=final_text,
        changed_files=changed,
        usage=usage,
    )
