# portable-agent-orchestrator

**將任何 Python 函式變為 LLM 可呼叫的工具 —— 僅需單一檔案，且執行期零依賴。**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Single file](https://img.shields.io/badge/core-1%20file%2C%20~200%20LOC-brightgreen)](orchestrator.py)
[![No deps](https://img.shields.io/badge/runtime%20deps-0-success)](requirements.txt)

> 繁體中文 ・ [English](README.md)

---

```python
from orchestrator import ToolRegistry, Orchestrator, AnthropicBackend

registry = ToolRegistry()

@registry.register("查詢客戶資料庫，回傳符合條件的前 N 筆。")
def search_customers(query: str, limit: int = 10, include_archived: bool = False) -> list:
    return db.query(query, limit=limit, archived=include_archived)

agent = Orchestrator(registry=registry, backend=AnthropicBackend(api_key="...", model="..."))
results = agent.run("幫我找最新 3 筆 acme 相關的客戶，封存的不要。")

for r in results:
    print(r.tool, r.arguments, "->", r.output)
# search_customers {'query': 'acme', 'limit': 3, 'include_archived': False} -> [...]
```

整個 API 就是這麼簡潔。一個 decorator、一個 `run()` 就搞定。必填參數、預設值乃至 JSON-Schema 型別，全都會從 function signature 自動推導 —— 你完全不需要手寫 tool spec。回傳的結果是普通的 dataclass，可以直接在應用程式的其他地方繼續使用。

## 為什麼有這個專案

你手邊已經有一堆能正常運作的內部腳本 —— 像是 Playwright 機器人、REST client 或 CSV 處理器。現在你想在這些腳本之上，加一個自然語言的操作入口。然而，你讀到的每一篇「agent 框架」教學，都預設你願意接受以下這些條件：

- 為了專案拉進 **80 個以上的間接依賴**（如 LangChain、LlamaIndex）
- 為了根本用不到的檢索功能，特地 **部署一個向量資料庫**
- 將自己 **綁死在某一家 LLM SDK** 上，日後想替換就得整個重寫
- 部署一個 **長期運行的服務**，即使其實一個 script 就綽綽有餘

這個專案採取的是完全相反的取捨：**它就是一個檔案，丟進你的專案資料夾裡就能用**。它甚至能運行在那些連 `pip install` 一個 500MB 相依套件都不可能的封閉環境中（例如 kiosk、操作員電腦或實體隔離網路 air-gap），而且完全不預設你明天是否還想繼續用同一家模型。

## 對比表

| | **portable-agent-orchestrator** | LangChain agents | LlamaIndex agents |
|---|---|---|---|
| 核心程式碼行數 | **~200** | 100,000+ | 80,000+ |
| 執行期必要依賴 | **0** | 30+ 個套件 | 25+ 個套件 |
| 安裝體積 | **~10 KB**（單一 .py 檔） | 數百 MB | 數百 MB |
| 冷啟動 import 時間 | **<10 ms**（沒有連鎖 import 效應） | 數秒（在慢速硬碟上更慘） | 數秒（在慢速硬碟上更慘） |
| 替換 LLM provider | **一個 60 行的 subclass** | 更換 import + wrapper + schema | 更換 import + wrapper + schema |
| 單一 hook 完成全稽核 | ✅ `on_call=...` | callback 散落各處 | callback 散落各處 |
| 一個下午即可讀完原始碼 | ✅ | ❌ | ❌ |

如果你要做的是「Notion RAG 搭配 Slack 串流回覆」那種複雜應用，請改用大型框架。但如果你只是想讓 LLM 能呼叫**你自己的**函式，這個專案就完全足夠了。

## 60 秒體驗

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

完全不需要 API key。內建的 `MockBackend` 會解析字面上的 `tool(arg=value)` 語法，藉此讓 registry → executor → audit hook 這整條 pipeline 完整地端到端跑過一次。當你準備好要消耗真實 token 時，換上 `AnthropicBackend`（或你自己寫的 backend）即可。

## 換上任何一家 LLM

模型供應商（provider）的實作只需要一個 method，完成它就大功告成了。

```python
class MyBackend(LLMBackend):
    def plan(self, user_input: str, tool_schemas: list[dict]) -> list[ToolCall]:
        # 呼叫你的模型，回傳它選的 tool calls
        ...
```

專案內建一個可直接使用的 `AnthropicBackend`（60 行）作為參考實作。**唯有當你實際用到它時**，才需要執行 `pip install anthropic` —— 核心的 orchestrator 與 `MockBackend` 始終維持零依賴。同樣的寫法也能輕鬆套用到 OpenAI、Gemini、vLLM、llama.cpp 或你自家的微調（fine-tuned）模型上。

## 結果是拿來用的，不只是印出來

每一次 tool call 都會回傳一個 `ExecutionResult`，讓你可以直接拿去運用：

```python
results = agent.run("找 acme 相關客戶，寄追蹤信給排第一的。")

for r in results:
    if r.error:
        log.warning("tool %s failed: %s", r.tool, r.error)
        continue
    metrics.timing(f"agent.{r.tool}.ms", r.duration_ms)
    pipeline.push(r.output)            # 直接傳遞至應用程式的其他地方
```

它就是一個普通的 dataclass，包含：`tool`、`arguments`、`output`、`error`、`duration_ms` 與 `call_id`。沒有多餘的 wrapper 物件、沒有需要 drain 的 async iterator，也沒有需要你記得註冊的 callback。

## 一行接上完整稽核

```python
def log_call(result):
    print(f"{result.tool}({result.arguments}) -> {result.output} [{result.duration_ms}ms]")

agent = Orchestrator(registry=registry, backend=backend, on_call=log_call)
```

每一次 tool 的執行都會經過 `on_call`。舉凡 logging、metrics、replay 或合規需求，全都仰賴這唯一的約定 —— 無論是把結果寫進 JSONL、推送到你的 metrics 後端，或進行任何其他處理，全都集中在這一個地方完成。

## 架構（全部就這些）

```
                +-------------------+
   user input ->|   LLMBackend      |--> List[ToolCall]
                +-------------------+
                          |
                          v
                +-------------------+         +----------------+
                |   Orchestrator    |-------->|   on_call hook |  (audit / metrics)
                +-------------------+         +----------------+
                          |
                          v
                +-------------------+
                |   ToolRegistry    |--> Tool.func(**arguments)
                +-------------------+
```

三個類別、三種職責，沒有繁複的繼承迷宮。想做 streaming、並行或重試嗎？只要 subclass `Orchestrator` 即可 —— 由於它的表面積極小，你大概一小時內就能 fork 出自己想要的版本。

## 誰適合用這個

✅ 你已經有能正常運作的內部自動化腳本，想在上面加一個自然語言介面
✅ 你的執行環境資源吃緊（如 kiosk、操作員桌面、air-gap），對依賴的大小錙銖必較
✅ 你想對不同的 LLM 廠商進行 A/B 測試，又不想重寫整個 agent 層
✅ 比起再學一套框架的心智模型，你寧願直接讀 200 行的程式碼

❌ 你需要開箱即用的 RAG、agent-of-agents、串流 UI 或長期狀態工作流
❌ 你樂於在 12 層的 `BaseChain.invoke()` 中進行 debug

## 目錄結構

```
portable-agent-orchestrator/
├── orchestrator.py        核心：ToolRegistry、LLMBackend、Orchestrator
├── examples/
│   ├── demo_tools.py      Sample tools
│   └── run_demo.py        End-to-end demo（用 MockBackend）
├── requirements.txt       Provider SDK（預設註解掉）
├── LICENSE                MIT
└── README.md / README.zh-TW.md
```

## 常見問題

**這個能上 production 嗎？** 核心非常精簡，你大可花點時間一氣呵成讀完，再自行決定。CI 在每次 push 時都會執行 demo。專案中沒有任何隱藏狀態、背景 thread 或全域 registry。

**那我直接用某家 provider 的 tool-calling API 不就好了？** 當然可以。這一層的作用只是將其包裝起來，讓「替換 provider」、「測試時 mock」與「稽核每一次呼叫」這三件事，各自都只需要一行程式碼就能搞定。

**可以加上 streaming 或並行處理嗎？** 可以，subclass `Orchestrator._execute` 即可。為了維持核心的可讀性，這部分並未放進主檔。

**授權？** MIT，請隨意使用。

## 貢獻

歡迎提出 Issue 與 PR。我們的底線是：核心維持單一檔案、執行期維持零依賴，且 core 不超過 250 行。一個功能若能透過 subclass 來實現，就不應該為它增加一個 flag。

## 授權

MIT。詳見 [LICENSE](LICENSE)。
