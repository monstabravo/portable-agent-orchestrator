# portable-agent-orchestrator

**Turn any Python function into an LLM-callable tool — in one file, with zero required dependencies.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Single file](https://img.shields.io/badge/core-1%20file%2C%20~200%20LOC-brightgreen)](orchestrator.py)
[![No deps](https://img.shields.io/badge/runtime%20deps-0-success)](requirements.txt)

> [繁體中文](README.zh-TW.md) ・ English

---

```python
from orchestrator import ToolRegistry, Orchestrator, AnthropicBackend

registry = ToolRegistry()

@registry.register("Search the customer database and return the top N matches.")
def search_customers(query: str, limit: int = 10, include_archived: bool = False) -> list:
    return db.query(query, limit=limit, archived=include_archived)

agent = Orchestrator(registry=registry, backend=AnthropicBackend(api_key="...", model="..."))
results = agent.run("Find me the latest 3 customers matching 'acme', skip archived ones.")

for r in results:
    print(r.tool, r.arguments, "->", r.output)
# search_customers {'query': 'acme', 'limit': 3, 'include_archived': False} -> [...]
```

That's the whole API. One decorator, one `run()`. Required arguments, optional defaults, and JSON-Schema types are all inferred from your function signature — you never write a tool spec by hand. Results come back as plain dataclasses you can keep using in the rest of your app.

## Why this exists

You already have a folder of internal scripts — a Playwright bot, a REST client, a CSV processor. You want a natural-language entry point on top of them. Every "agent framework" tutorial you read assumes you're happy to:

- Pull in **80+ transitive dependencies** (LangChain, LlamaIndex)
- Run a **vector database** for things that don't need retrieval
- Lock yourself to **one LLM SDK** forever
- Deploy a **long-running service** when a script would do

This project is the opposite trade-off. It's a single file you drop into a project. It works on a locked-down operator desktop where `pip install` of a 500MB tree is a non-starter. And it makes no assumption about which model you want to use tomorrow.

## Feature comparison

| | **portable-agent-orchestrator** | LangChain agents | LlamaIndex agents |
|---|---|---|---|
| Lines of core code | **~200** | 100,000+ | 80,000+ |
| Required runtime deps | **0** | 30+ | 25+ |
| Install footprint | **~10 KB** (one .py file) | 100s of MB | 100s of MB |
| Cold-start import time | **<10 ms** (no import waterfall) | seconds, on slow disks | seconds, on slow disks |
| Swap LLM provider | **one 60-line subclass** | new imports + wrappers + schemas | new imports + wrappers + schemas |
| Auditable in one hook | ✅ `on_call=...` | scattered callbacks | scattered callbacks |
| Reads as one afternoon's code | ✅ | ❌ | ❌ |

If you need RAG-over-Notion-with-streaming-Slack-replies, use the big frameworks. If you need an LLM to call **your** functions, this is enough.

## 60-second tour

```bash
git clone https://github.com/monstabravo/portable-agent-orchestrator
cd portable-agent-orchestrator/examples
python run_demo.py
```

```
User input: add(a=3, b=5); echo(text='hello'); list_files(directory='.')

  [OK] add({'a': 3, 'b': 5}) -> 8 (0ms)
  [OK] echo({'text': 'hello'}) -> hello (0ms)
  [OK] list_files({'directory': '.'}) -> ['demo_tools.py', 'run_demo.py'] (1ms)
```

No API key needed. The bundled `MockBackend` parses literal `tool(arg=value)` syntax so the registry → executor → audit-hook pipeline is exercised end to end. Swap in `AnthropicBackend` (or your own) when you're ready to spend real tokens.

## Plug in any LLM

The provider is one method. Implement it, you're done.

```python
class MyBackend(LLMBackend):
    def plan(self, user_input: str, tool_schemas: list[dict]) -> list[ToolCall]:
        # Call your model. Return the tool calls it picked.
        ...
```

A working `AnthropicBackend` is included (60 lines) as a reference implementation. It needs `pip install anthropic` only if you actually use it — the core orchestrator and the `MockBackend` stay zero-dep. The same shape works for OpenAI, Gemini, vLLM, llama.cpp, or your in-house fine-tune.

## Use the results, don't just print them

Every tool call returns an `ExecutionResult` you can keep using:

```python
results = agent.run("Find acme customers and email the top one a follow-up.")

for r in results:
    if r.error:
        log.warning("tool %s failed: %s", r.tool, r.error)
        continue
    metrics.timing(f"agent.{r.tool}.ms", r.duration_ms)
    pipeline.push(r.output)            # feed straight into the rest of your app
```

It's a plain dataclass: `tool`, `arguments`, `output`, `error`, `duration_ms`, `call_id`. No wrapper objects, no async iterators to drain, no callbacks to remember to register.

## Audit everything in one line

```python
def log_call(result):
    print(f"{result.tool}({result.arguments}) -> {result.output} [{result.duration_ms}ms]")

agent = Orchestrator(registry=registry, backend=backend, on_call=log_call)
```

Every executed tool call goes through `on_call`. That's the only contract for logging, metrics, replay, or compliance — write the results to JSONL, push to your metrics backend, or anything else, in one place.

## Architecture (the whole thing)

```
                +-------------------+
  user input -> |   LLMBackend      |  -> List[ToolCall]
                +-------------------+
                          |
                          v
                +-------------------+         +----------------+
                |   Orchestrator    |  -----> |   on_call hook |  (audit / metrics)
                +-------------------+         +----------------+
                          |
                          v
                +-------------------+
                |   ToolRegistry    |  -> Tool.func(**arguments)
                +-------------------+
```

Three classes, three responsibilities, no inheritance maze. Want streaming, parallel execution, retries? Subclass `Orchestrator` — there's so little surface area you can fork it in an hour.

## Who this is for

✅ You ship internal automation that already works and want an NL front-end on top
✅ You operate in environments where dependency footprint matters (kiosks, operator desktops, air-gapped)
✅ You want to A/B different LLM providers without rewriting the agent layer
✅ You'd rather read 200 lines than learn another framework's mental model

❌ You need RAG, agent-of-agents, streaming UI, or long-running stateful workflows out of the box
❌ You enjoy debugging through 12 layers of `BaseChain.invoke()`

## Layout

```
portable-agent-orchestrator/
├── orchestrator.py        Core: ToolRegistry, LLMBackend, Orchestrator
├── examples/
│   ├── demo_tools.py      Sample tools registered against the registry
│   └── run_demo.py        End-to-end demo using MockBackend
├── requirements.txt       Optional provider SDKs (commented out by default)
├── LICENSE                MIT
└── README.md / README.zh-TW.md
```

## FAQ

**Is this production-ready?** The core is small enough to audit in one sitting — read it and decide. CI runs the demo on every push. There's no hidden state, no background thread, no global registry.

**Why not just use a provider's tool-calling API directly?** You can. This wraps it so swapping providers, mocking for tests, and auditing every call is one line each.

**Can I add streaming / parallel calls?** Yes — subclass `Orchestrator._execute`. Kept out of core to keep core readable.

**License?** MIT. Use it however you want.

## Contributing

Issues and PRs welcome. The bar is: stays single-file, stays zero-dep at runtime, stays under 250 LOC for the core. If a feature can be a subclass instead of a flag, it should be.

## License

MIT. See [LICENSE](LICENSE).
