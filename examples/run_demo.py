"""Run a minimal end-to-end demo without requiring any API key.

The MockBackend parses literal `tool_name(arg=value)` syntax, so the demo proves
the registry + executor + audit-hook pipeline is wired correctly without
depending on a paid LLM.

Run from this directory:
    python run_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running this file directly without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import MockBackend, Orchestrator, results_to_json  # noqa: E402

from demo_tools import registry  # noqa: E402


def audit_hook(result) -> None:
    status = "OK" if not result.error else "ERR"
    print(f"  [{status}] {result.tool}({result.arguments}) -> {result.output} ({result.duration_ms}ms)")


def main() -> None:
    orchestrator = Orchestrator(registry=registry, backend=MockBackend(), on_call=audit_hook)
    user_input = "add(a=3, b=5); echo(text='hello'); list_files(directory='.')"
    print(f"User input: {user_input}\n")
    results = orchestrator.run(user_input)
    print("\nFinal JSON payload:\n")
    print(results_to_json(results))


if __name__ == "__main__":
    main()
