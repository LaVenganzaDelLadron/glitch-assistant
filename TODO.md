# Tool Calling Implementation — ✅ Complete

| # | File | Status |
|---|------|--------|
| 1 | `app/core/models/tool_call.py` — Added `id`, `to_dict()` | ✅ |
| 2 | `app/core/models/message.py` — Added `tool_call_id`, `tool_calls`, updated `to_dict()` | ✅ |
| 3 | `app/core/memory/conversation.py` — Added `add_tool()`, extended `add_assistant()` | ✅ |
| 4 | `app/tools/base.py` — Added `ToolOperation`, `Tool.operations()` | ✅ |
| 5 | `app/tools/filesystem.py` — Refactored to operations (read_file, write_file, exists, list_directory) | ✅ |
| 6 | `app/tools/terminal.py` — Refactored to operations (run) | ✅ |
| 7 | `app/tools/git.py` — Refactored to operations (run) | ✅ |
| 8 | `app/tools/registry.py` — Operation-based, `schemas()`, `execute(name, **kwargs)` | ✅ |
| 9 | `app/core/ai/base.py` — Added `tools` param to `generate()` | ✅ |
| 10 | `app/core/ai/groq.py` — Sends tools, parses tool_calls, fixed content bug | ✅ |
| 11 | `app/core/pipeline/executor.py` — Tool loop with MAX_TOOL_STEPS=10 | ✅ |
| 12 | `app/core/pipeline/pipeline.py` — Injects registry into Executor | ✅ |
| 13 | `main.py` — Injects registry into Pipeline | ✅ |

