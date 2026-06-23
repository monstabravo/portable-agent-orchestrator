"""Portable Agent Orchestrator — minimal LLM function-calling runtime."""

from __future__ import annotations

import ast
import inspect
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional


# --- Tool registry -----------------------------------------------------------

_PY_TO_JSON = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


@dataclass
class Tool:
    name: str
    description: str
    func: Callable[..., Any]
    schema: Dict[str, Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, description: str = "", name: Optional[str] = None) -> Callable:
        """Decorator: register a function as an LLM-callable tool."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or func.__name__
            desc = description or (func.__doc__ or "").strip()
            self._tools[tool_name] = Tool(
                name=tool_name,
                description=desc,
                func=func,
                schema=self._build_schema(func, desc),
            )
            return func

        return decorator

    def _build_schema(self, func: Callable, description: str) -> Dict[str, Any]:
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for pname, param in inspect.signature(func).parameters.items():
            anno = param.annotation if param.annotation is not inspect.Parameter.empty else str
            properties[pname] = {"type": _PY_TO_JSON.get(anno, "string")}
            if param.default is inspect.Parameter.empty:
                required.append(pname)
        return {
            "name": func.__name__,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        }

    def list_schemas(self) -> List[Dict[str, Any]]:
        return [t.schema for t in self._tools.values()]

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def names(self) -> List[str]:
        return list(self._tools.keys())


# --- LLM backend abstraction -------------------------------------------------


@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any]
    call_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


class LLMBackend:
    """Subclass and implement `plan` to support a real provider."""

    def plan(self, user_input: str, tool_schemas: List[Dict[str, Any]]) -> List[ToolCall]:
        raise NotImplementedError


class MockBackend(LLMBackend):
    """Deterministic backend that scans `user_input` for `tool_name(...)` calls.

    Intended only for unit tests / demos without an API key. It is *not* a real
    intent parser — the user has to type the call in syntactic form.
    """

    _CALL_RE = re.compile(r"(\w+)\((.*?)\)")
    _BARE = {"true": True, "false": False, "True": True, "False": False, "None": None}

    def plan(self, user_input: str, tool_schemas: List[Dict[str, Any]]) -> List[ToolCall]:
        return [
            ToolCall(name=m.group(1), arguments=self._parse_args(m.group(2)))
            for m in self._CALL_RE.finditer(user_input)
        ]

    @staticmethod
    def _parse_args(args_raw: str) -> Dict[str, Any]:
        args_raw = args_raw.strip()
        if not args_raw:
            return {}
        try:
            call = ast.parse(f"_f({args_raw})", mode="eval").body
        except SyntaxError:
            return {}
        result: Dict[str, Any] = {}
        for kw in call.keywords:
            if not kw.arg:
                continue
            raw = ast.unparse(kw.value)
            if raw in MockBackend._BARE:
                result[kw.arg] = MockBackend._BARE[raw]
                continue
            try:
                result[kw.arg] = ast.literal_eval(kw.value)
            except (ValueError, SyntaxError):
                result[kw.arg] = raw
        return result


class AnthropicBackend(LLMBackend):
    """Example backend for the Anthropic SDK. Requires `pip install anthropic`,
    an API key, and a model id you pass in explicitly."""

    def __init__(self, api_key: str, model: str) -> None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise ImportError("Install with: pip install anthropic") from exc
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def plan(self, user_input: str, tool_schemas: List[Dict[str, Any]]) -> List[ToolCall]:
        tools_payload = [
            {"name": s["name"], "description": s["description"], "input_schema": s["parameters"]}
            for s in tool_schemas
        ]
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            tools=tools_payload,
            messages=[{"role": "user", "content": user_input}],
        )
        return [
            ToolCall(name=block.name, arguments=dict(block.input or {}), call_id=block.id)
            for block in response.content
            if getattr(block, "type", None) == "tool_use"
        ]


# --- Executor ----------------------------------------------------------------


@dataclass
class ExecutionResult:
    call_id: str
    tool: str
    arguments: Dict[str, Any]
    output: Any
    error: Optional[str]
    duration_ms: int


class Orchestrator:
    def __init__(
        self,
        registry: ToolRegistry,
        backend: LLMBackend,
        on_call: Optional[Callable[[ExecutionResult], None]] = None,
    ) -> None:
        self.registry = registry
        self.backend = backend
        self.on_call = on_call

    def run(self, user_input: str) -> List[ExecutionResult]:
        calls = self.backend.plan(user_input, self.registry.list_schemas())
        return [self._execute(call) for call in calls]

    def _execute(self, call: ToolCall) -> ExecutionResult:
        tool = self.registry.get(call.name)
        if tool is None:
            return ExecutionResult(call.call_id, call.name, call.arguments, None, f"tool not found: {call.name}", 0)
        start = time.perf_counter()
        try:
            output, error = tool.func(**call.arguments), None
        except Exception as exc:  # noqa: BLE001
            output, error = None, f"{type(exc).__name__}: {exc}"
        result = ExecutionResult(
            call.call_id, call.name, call.arguments, output, error,
            int((time.perf_counter() - start) * 1000),
        )
        if self.on_call:
            try:
                self.on_call(result)
            except Exception:  # noqa: BLE001 - logging must not break the run
                pass
        return result


def results_to_json(results: List[ExecutionResult]) -> str:
    return json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2)
