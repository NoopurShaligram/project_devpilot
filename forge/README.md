# Forge — Phase 2

Phase 2 turns Forge from an advisor into a bounded agentic software-development workflow.

## What it does

For executable coding tasks:

`Task → Analyze → Policy → Load project instructions → Plan → Human approval → Implement → Test → Review → Human approval`

Test failures can send the workflow back to the implementer, with a bounded number of repair attempts. Final-review change requests can also loop back to implementation, with a bounded number of review cycles.

For explanation-only tasks, Forge stays in advice mode and does not modify the repository.

## Important safety boundary

The implementation agent can only use these local tools:

- `list_files`
- `read_file`
- `write_file`
- `run_tests` (pytest only)
- `git_status`

It cannot commit, push, deploy, install packages, or read/write protected secret files. This is a local Phase 2 sandbox, not a production-safe executor.

## Install

```powershell
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
```

Put your model credentials and model name in `.env`.

SQLite checkpoint support is used so an interrupted workflow can be resumed from another CLI/API process.

## Run the demo

From this repository root:

```powershell
forge run --root demo_project "Fix the add function so negative numbers work correctly and keep the regression test"
```

Forge will pause at the plan-approval interrupt and print a `THREAD_ID`.

Resume it with:

```powershell
forge resume <THREAD_ID> --approved --note "Plan approved"
```

At final review, Forge will print the diff, test result, and reviewer report.

Then resume with one of:

```powershell
forge resume <THREAD_ID> --decision approved --note "Final diff reviewed"
forge resume <THREAD_ID> --decision request_changes --note "Add another edge-case test"
forge resume <THREAD_ID> --decision rejected --note "Do not continue"
```

## API

```powershell
uvicorn forge_advisor.api:app --reload
```

Then use:

- `POST /advise`
- `POST /runs`
- `POST /runs/{thread_id}/resume`
- `GET /health`

## Architecture

```text
Developer
   │
   ▼
Task Analyzer (LLM)
   │
   ▼
Deterministic Policy
   │
   ├── advice-only ───────────────────────► END
   │
   ▼
Project Instructions
   │
   ▼
Planner (LLM)
   │
   ▼
HUMAN APPROVAL
   │
   ▼
Baseline Snapshot
   │
   ▼
Implementer Agent
   │       │
   │       └── read/list/write/pytest tools
   ▼
Test Runner
   │
   ├── failed + attempts remaining ───────► Implementer
   │
   ▼
Reviewer (LLM)
   │
   ▼
HUMAN FINAL REVIEW
   │
   ├── request_changes + cycles remaining ► Implementer
   ├── rejected ──────────────────────────► END
   └── approved ──────────────────────────► END
```

## Why LangGraph?

The graph is stateful and interruptible. Human approvals are implemented with `interrupt()` and resumed with `Command(resume=...)`. A SQLite checkpointer persists thread state across processes.

## Phase 2 intentionally does not include

- MCP
- GitHub/Slack/Jira connectors
- automatic commits or PR creation
- deployment
- long-term memory
- production-grade sandboxing

Those belong after the execution loop is stable.
