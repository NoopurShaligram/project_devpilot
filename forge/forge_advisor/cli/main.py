import argparse
import json
import sys
from uuid import uuid4

from langgraph.types import Command

from forge_advisor.runtime import graph_runtime


def _json_default(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return str(value)


def _print_result(thread_id: str, result: dict) -> None:
    interrupts = result.get("__interrupt__", ())
    if interrupts:
        print(f"\nTHREAD_ID={thread_id}")
        print("\nForge is waiting for human input:\n")
        for item in interrupts:
            print(json.dumps({
                "id": getattr(item, "id", None),
                "value": getattr(item, "value", item),
                "response_schema": getattr(item, "response_schema", None),
            }, indent=2, default=_json_default))
        return

    output = {
        "thread_id": thread_id,
        "status": result.get("status"),
        "advisor": result.get("advisor"),
        "plan": result.get("plan"),
        "implementation": result.get("implementation"),
        "test_result": result.get("test_result"),
        "review": result.get("review"),
        "diff": result.get("diff"),
        "usage": result.get("usage"),
    }
    print(json.dumps(output, indent=2, default=_json_default))


def _run(args):
    thread_id = str(uuid4())
    with graph_runtime() as graph:
        result = graph.invoke(
            {"task": args.task, "project_root": args.root},
            config={"configurable": {"thread_id": thread_id}},
        )
    _print_result(thread_id, result)


def _resume(args):
    if args.approved:
        payload = {"approved": True, "note": args.note}
    elif args.rejected:
        payload = {"approved": False, "note": args.note}
    elif args.decision:
        payload = {"decision": args.decision, "note": args.note}
    else:
        raise SystemExit("Provide --approved, --rejected, or --decision")

    with graph_runtime() as graph:
        result = graph.invoke(
            Command(resume=payload),
            config={"configurable": {"thread_id": args.thread_id}},
        )
    _print_result(args.thread_id, result)


def _advise(args):
    # Backwards-compatible Phase 1-style advisory command.
    with graph_runtime() as graph:
        result = graph.invoke(
            {"task": args.task, "project_root": args.root},
            config={"configurable": {"thread_id": str(uuid4())}},
        )
    print(json.dumps({
        "status": result.get("status"),
        "advisor": result.get("advisor"),
    }, indent=2, default=_json_default))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Forge — AI development workflow orchestrator"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    advise = sub.add_parser("advise", help="Advise without execution")
    advise.add_argument("task")
    advise.add_argument("--root", default=".")
    advise.set_defaults(func=_advise)

    run = sub.add_parser("run", help="Run an agentic development workflow")
    run.add_argument("task")
    run.add_argument("--root", default=".")
    run.set_defaults(func=_run)

    resume = sub.add_parser("resume", help="Resume a paused workflow")
    resume.add_argument("thread_id")
    resume.add_argument("--approved", action="store_true")
    resume.add_argument("--rejected", action="store_true")
    resume.add_argument(
        "--decision",
        choices=["approved", "request_changes", "rejected"],
    )
    resume.add_argument("--note", default="")
    resume.set_defaults(func=_resume)

    args = parser.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
