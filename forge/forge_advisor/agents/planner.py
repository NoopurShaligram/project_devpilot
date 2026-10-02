from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from forge_advisor.config import settings
from forge_advisor.models.domain import (
    AdvisorResponse,
    ImplementationPlan,
    PlanStep,
    TaskAnalysis,
)

PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are Forge's software architecture planner.

Create an implementation plan for the developer task.
Do not write code. Do not claim to know files you have not been shown.
Use the existing task analysis, project instructions, and advisor recommendation.
Prefer the smallest safe change.
Explicitly identify assumptions, acceptance criteria, risks, and rollback strategy.
""".strip(),
        ),
        (
            "human",
            """
TASK:
{task}

TASK ANALYSIS:
{analysis}

ADVISOR RECOMMENDATION:
{advisor}

PROJECT INSTRUCTIONS:
{instructions}
""".strip(),
        ),
    ]
)


def _fallback_plan(task: str, analysis: TaskAnalysis, advisor: AdvisorResponse) -> ImplementationPlan:
    if analysis.category.value == "debugging":
        steps = [
            PlanStep(id=1, name="Inspect", objective="Inspect the relevant code and tests.", responsible_role="architect", expected_output="Root cause hypothesis"),
            PlanStep(id=2, name="Fix", objective="Implement the smallest corrective change.", responsible_role="implementer", expected_output="Updated source and/or tests"),
            PlanStep(id=3, name="Test", objective="Run the relevant pytest suite.", responsible_role="tester", expected_output="Passing test results"),
            PlanStep(id=4, name="Review", objective="Review the final diff for correctness and architecture compliance.", responsible_role="reviewer", expected_output="Review report"),
        ]
    else:
        steps = [
            PlanStep(id=1, name="Inspect", objective="Inspect the repository structure and relevant files.", responsible_role="architect", expected_output="Affected-file map"),
            PlanStep(id=2, name="Implement", objective="Implement the requested change using the project conventions.", responsible_role="implementer", expected_output="Updated source and tests"),
            PlanStep(id=3, name="Test", objective="Run the relevant pytest suite.", responsible_role="tester", expected_output="Test results"),
            PlanStep(id=4, name="Review", objective="Review the final diff for correctness and architecture compliance.", responsible_role="reviewer", expected_output="Review report"),
        ]

    return ImplementationPlan(
        summary=f"Plan for: {task}",
        assumptions=["The repository contains the code relevant to the requested task."],
        acceptance_criteria=[
            "The requested behavior is implemented.",
            "Relevant automated tests pass.",
            "The final diff follows project instructions.",
        ],
        risks=advisor.approval_points,
        rollback_strategy="Revert the working-tree changes from this run before merge.",
        steps=steps,
    )


def generate_plan(
    task: str,
    analysis: TaskAnalysis,
    advisor: AdvisorResponse,
    instructions: str,
) -> tuple[ImplementationPlan, dict[str, int]]:
    if not settings.openai_api_key or not settings.llm_model:
        return _fallback_plan(task, analysis, advisor), {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "model_calls": 0}

    model = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )
    structured = model.with_structured_output(
        ImplementationPlan,
        include_raw=True,
    )
    result = (PROMPT | structured).invoke(
        {
            "task": task,
            "analysis": analysis.model_dump_json(indent=2),
            "advisor": advisor.model_dump_json(indent=2),
            "instructions": instructions or "No project instruction files were found.",
        }
    )

    parsed = result["parsed"]
    raw = result.get("raw")
    usage = getattr(raw, "usage_metadata", None) or {}
    return parsed, {
        "input_tokens": int(usage.get("input_tokens", 0)),
        "output_tokens": int(usage.get("output_tokens", 0)),
        "total_tokens": int(usage.get("total_tokens", 0)),
        "model_calls": 1,
    }
