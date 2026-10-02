from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from forge_advisor.config import settings
from forge_advisor.models.domain import ImplementationPlan, ReviewReport, UsageTotals

PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are Forge's independent code reviewer.

Review the implementation against:
- the approved plan
- project instructions
- test results
- the actual diff

Do not propose unrelated rewrites.
Flag correctness, architecture, security, test coverage, and maintainability issues.
Be conservative: request changes only when there is a concrete issue.
""".strip(),
        ),
        (
            "human",
            """
APPROVED PLAN:
{plan}

PROJECT INSTRUCTIONS:
{instructions}

TEST RESULT:
{test_result}

DIFF:
{diff}
""".strip(),
        ),
    ]
)


def review_changes(
    plan: ImplementationPlan,
    instructions: str,
    test_result: str,
    diff: str,
) -> tuple[ReviewReport, UsageTotals]:
    if not settings.openai_api_key or not settings.llm_model:
        passed = "passed" in test_result.lower() and "exit_code=0" in test_result.lower()
        report = ReviewReport(
            decision="approve" if passed else "changes_requested",
            summary=(
                "Fallback review: tests passed, so no blocking issue was detected."
                if passed
                else "Fallback review: tests did not pass."
            ),
            architecture_compliant=True,
            tests_adequate=passed,
            issues=[] if passed else [
                {
                    "severity": "high",
                    "file": None,
                    "issue": "Automated tests did not pass.",
                    "recommendation": "Resolve test failures before accepting the implementation.",
                }
            ],
        )
        return report, UsageTotals()

    model = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )
    structured = model.with_structured_output(
        ReviewReport,
        include_raw=True,
    )

    result = (PROMPT | structured).invoke(
        {
            "plan": plan.model_dump_json(indent=2),
            "instructions": instructions or "No instruction files were found.",
            "test_result": test_result,
            "diff": diff[-30000:],
        }
    )

    raw = result.get("raw")
    usage = getattr(raw, "usage_metadata", None) or {}
    totals = UsageTotals(
        input_tokens=int(usage.get("input_tokens", 0)),
        output_tokens=int(usage.get("output_tokens", 0)),
        total_tokens=int(usage.get("total_tokens", 0)),
        model_calls=1,
    )
    return result["parsed"], totals
