# Forge — Phase 1: AI Development Advisor

Forge analyzes a natural-language developer task and recommends **how the task should be handled with AI** before any autonomous execution is allowed.

## Phase 1 output

For each task, Forge returns:

- semantic task category
- recommended interface: chat / IDE agent / coding agent
- required capabilities
- recommended workflow
- deterministic risk level
- human approval points
- rationale

## Architecture

```text
Developer task
      |
      v
 LangGraph
      |
      +--> Task Analyzer (LLM)
      |       |
      |       +--> structured TaskAnalysis
      |
      +--> Policy Engine (Python)
              |
              +--> interface
              +--> workflow
              +--> risk
              +--> approval gates
              +--> capabilities
```

**Important:** the LLM interprets the request; the deterministic policy engine makes the final risk/approval decision.

## Setup

```powershell
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
```

Put your model credentials in `.env`:

```env
OPENAI_API_KEY=...
LLM_MODEL=...
```

The project still runs without these variables by using the deterministic heuristic analyzer.

## Run the CLI

```powershell
forge "Implement OAuth login in my FastAPI backend and run tests"
```

or:

```powershell
python -m forge_advisor.cli.main "Deploy this service to production"
```

## Run the API

```powershell
uvicorn forge_advisor.api:app --reload
```

Then open:

```text
http://127.0.0.1:8000/docs
```

POST `/advise` with:

```json
{
  "task": "Add OAuth login to my FastAPI backend and run tests"
}
```

## Run tests

```powershell
pytest -q
```

## Next step

Phase 1B should add a proper evaluation runner over `examples/evaluation.jsonl`, then a UI. Phase 2 can add real project context, MCP capability discovery, and execution.
