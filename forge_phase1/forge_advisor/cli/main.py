import argparse
import json

from forge_advisor.graph.workflow import graph


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ask Forge how an AI-assisted development task should be handled."
    )
    parser.add_argument("task", nargs="+", help="The developer task in natural language")
    args = parser.parse_args()

    task = " ".join(args.task)
    result = graph.invoke({"task": task})
    print(json.dumps(result["response"].model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
