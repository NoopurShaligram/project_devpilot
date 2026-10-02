from fastapi import FastAPI
from pydantic import BaseModel, Field

from forge_advisor.graph.workflow import graph
from forge_advisor.models.domain import AdvisorResponse


app = FastAPI(
    title="Forge AI Development Advisor",
    version="0.1.0",
    description="Recommends an AI-assisted software-development workflow before autonomous execution.",
)


class AdviceRequest(BaseModel):
    task: str = Field(min_length=3, max_length=10_000)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/advise", response_model=AdvisorResponse)
def advise(request: AdviceRequest) -> AdvisorResponse:
    result = graph.invoke({"task": request.task})
    return result["response"]
