"""Example tools to demonstrate the registry + orchestrator wiring."""

from __future__ import annotations

from pathlib import Path

from orchestrator import ToolRegistry


registry = ToolRegistry()


@registry.register("Add two integers and return the sum.")
def add(a: int, b: int) -> int:
    return a + b


@registry.register("Echo a piece of text back to the caller.")
def echo(text: str) -> str:
    return text


@registry.register("List filenames in a directory (non-recursive).")
def list_files(directory: str) -> list:
    p = Path(directory)
    if not p.exists():
        raise FileNotFoundError(directory)
    return sorted(
        entry.name
        for entry in p.iterdir()
        if not entry.name.startswith(".") and entry.name != "__pycache__"
    )


@registry.register("Read a UTF-8 text file and return its first N characters.")
def read_head(path: str, n_chars: int = 200) -> str:
    return Path(path).read_text(encoding="utf-8")[:n_chars]
