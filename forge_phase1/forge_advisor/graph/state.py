from typing import TypedDict

from forge_advisor.models.domain import AdvisorResponse, TaskAnalysis


class AdvisorState(TypedDict, total=False):
    task: str
    analysis: TaskAnalysis
    response: AdvisorResponse
