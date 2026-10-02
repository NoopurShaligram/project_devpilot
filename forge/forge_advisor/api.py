from uuid import uuid4

from fastapi import FastAPI, HTTPException
from langgraph.types import Command
from pydantic import BaseModel, Field

from forge_advisor.runtime import graph_runtime

app = FastAPI(
    title="Forge AI Development Advisor",
    version="0.2.0",
)


class RunRequest(BaseModel):
    task: str = Field(min_length=3, max_length=10_000)
    project_root: str = "."


class ResumeRequest(BaseModel):
    approved: bool | None = None
    decision: str | None = None
    note: str = ""


def _interrupts(result: dict) -> list[dict]:
    output = []
    for item in result.get("__interrupt__", ()):
        output.append(
            {
                "id": getattr(item, "id", None),
                "value": getattr(item, "value", item),
                "response_schema": getattr(item, "response_schema", None),
            }
        )
    return output


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/advise")
def advise(request: RunRequest):
    with graph_runtime() as graph:
        result = graph.invoke(
            {"task": request.task, "project_root": request.project_root},
            config={"configurable": {"thread_id": str(uuid4())}},
        )
    return {
        "status": result.get("status", "unknown"),
        "advisor": result.get("advisor"),
    }


@app.post("/runs")
def start_run(request: RunRequest):
    thread_id = str(uuid4())
    with graph_runtime() as graph:
        result = graph.invoke(
            {"task": request.task, "project_root": request.project_root},
            config={"configurable": {"thread_id": thread_id}},
        )

    return {
        "thread_id": thread_id,
        "status": "awaiting_human" if result.get("__interrupt__") else result.get("status", "unknown"),
        "advisor": result.get("advisor"),
        "plan": result.get("plan"),
        "interrupts": _interrupts(result),
        "test_result": result.get("test_result"),
        "review": result.get("review"),
    }


@app.post("/runs/{thread_id}/resume")
def resume_run(thread_id: str, request: ResumeRequest):
    if request.approved is not None:
        payload = {"approved": request.approved, "note": request.note}
    elif request.decision in {"approved", "request_changes", "rejected"}:
        payload = {"decision": request.decision, "note": request.note}
    else:
        raise HTTPException(status_code=400, detail="Provide approved or a valid decision")

    with graph_runtime() as graph:
        result = graph.invoke(
            Command(resume=payload),
            config={"configurable": {"thread_id": thread_id}},
        )

    return {
        "thread_id": thread_id,
        "status": "awaiting_human" if result.get("__interrupt__") else result.get("status", "unknown"),
        "interrupts": _interrupts(result),
        "implementation": result.get("implementation"),
        "test_result": result.get("test_result"),
        "review": result.get("review"),
        "diff": result.get("diff"),
        "usage": result.get("usage"),
    }
