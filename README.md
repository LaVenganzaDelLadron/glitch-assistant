# Glitch Assistant

An extensible, AI-powered command-line and web assistant for software engineering and cybersecurity. Built on Groq's LLM API with a modular pipeline architecture, intent routing, tool-calling capabilities, and token-aware context management.

![Glitch Assistant demo](glitch.gif)

## Features

- **Dual Interface** — CLI (`python main.py`) for terminal-first users and Web UI (`python main.py --web`) with a FastAPI-powered chat interface
- **Intent Routing** — Automatically detects the nature of your request and loads specialized prompts for: general chat, code review, debugging, documentation, planning, and security analysis
- **Tool-Calling** — The AI can use filesystem, terminal, and Git tools in a loop to gather information and take actions on your behalf
- **Token Budget Management** — Automatically estimates context size, trims older conversation history, and reserves tokens to stay within the model's context window
- **Smart Output Compression** — Binary, JSON, and HTML content is automatically summarized before being fed back to the LLM, preventing context overflow
- **Conversation Memory** — Maintains a rolling window of recent messages (default: 20) for coherent multi-turn interactions
- **Project Context Awareness** — Tracks the current project's root, language, framework, and Git repository metadata
- **Extensible Architecture** — Easy to add new LLM providers, tools, routes, and prompt templates

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                     Interfaces                        │
│  ┌──────────────┐          ┌──────────────────────┐  │
│  │  CLI (main)  │          │  Web (FastAPI)       │  │
│  │  python main │          │  python main --web   │  │
│  └──────┬───────┘          └──────────┬───────────┘  │
└─────────┼──────────────────────────────┼──────────────┘
          │                              │
          └──────────┬───────────────────┘
                     │
          ┌──────────▼──────────┐
          │   Application       │  ← create_pipeline() wires everything
          │   (app/application) │
          └──────────┬──────────┘
                     │
          ┌──────────▼─────────────────────────────────┐
          │                Pipeline                      │
          │                                              │
          │  ┌────────┐    ┌──────────┐  ┌──────────┐  │
          │  │ Router │───▶│ Pipeline │─▶│ Executor │  │
          │  │(intent │    │ (orchest)│  │(tool     │  │
          │  │ detect)│    │          │  │  loop)   │  │
          │  └────────┘    └──────────┘  └────┬─────┘  │
          │                                    │        │
          │  ┌──────────────────────────┐      │        │
          │  │    ContextBuilder        │◄─────┘        │
          │  │  (token budget + trim)   │               │
          │  └──────────────────────────┘               │
          └─────────────────────────────────────────────┘
                     │
          ┌──────────▼──────────┐
          │    LLM Provider      │
          │  ┌────────────────┐  │
          │  │   Groq (via    │  │
          │  │  OpenAI SDK)   │  │
          │  └────────────────┘  │
          └──────────────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
┌────▼────┐   ┌─────▼─────┐   ┌─────▼────┐
│ Memory  │   │   Tools    │   │  Prompts  │
│         │   │            │   │          │
│ • Conv  │   │ • File     │   │ • System │
│ • Proj  │   │ • Terminal │   │ • Chat   │
│ • VecDB │   │ • Git      │   │ • Review │
│         │   │            │   │ • Debug  │
│         │   │            │   │ • Plan   │
│         │   │            │   │ • Sec    │
└─────────┘   └────────────┘   └──────────┘
```

### Component Overview

| Layer | Directory | Purpose |
|-------|-----------|---------|
| **Interfaces** | `app/interfaces/` | CLI (`python main.py`) and Web UI (`python main.py --web`) entry points |
| **Application** | `app/application.py` | Dependency injection — wires the Pipeline with LLM, memory, and tools |
| **Pipeline** | `app/core/pipeline/` | Core orchestration: `Router` (intent detection), `Pipeline` (orchestrator), `Executor` (tool-calling loop), `ContextBuilder` (token budget) |
| **AI Providers** | `app/core/ai/` | Pluggable LLM backends. Currently ships with `GroqProvider` (OpenAI-compatible API). Extend via `LLMFactory` |
| **Memory** | `app/core/memory/` | `ConversationMemory` (deque-based, token-aware trimming), `ProjectMemory` (project context), vector store & embeddings for RAG |
| **Tools** | `app/tools/` | Extensible tool system. Built-in: `FileSystemTool`, `TerminalTool`, `GitTool`. Registered via `ToolRegistry` |
| **Prompts** | `prompts/` | Markdown prompt templates loaded dynamically by intent: `chat`, `code_review`, `debugging`, `documentation`, `planner`, `security`, `system` |
| **Models** | `app/core/models/` | Data classes: `Message`, `AIResponse`, `ToolCall`, `Usage` |
| **Utilities** | `app/core/utils/` | `OutputCompressor` — detects binary/JSON/HTML, applies smart summarization |

### Intent Routing

The Router analyzes user input for keywords and selects an appropriate prompt template:

| Keyword Detected | Route / Task | Prompt Template |
|-----------------|--------------|-----------------|
| `security` | security | `prompts/security.md` |
| `planner` / `plan` | planner | `prompts/planner.md` |
| `review` / `code review` | code_review | `prompts/code_review.md` |
| `debug` / `debugging` | debugging | `prompts/debugging.md` |
| `document` / `documentation` | documentation | `prompts/documentation.md` |
| *(default)* | chat | `prompts/chat.md` |

### Tool-Calling Loop

The Executor runs a loop (up to 10 iterations per prompt):

1. Store the user message in conversation memory
2. Build an optimized context (with token budget enforcement)
3. Call the LLM with tool schemas
4. If the LLM requests tool calls, execute each one and compress the output
5. Append tool results back into conversation memory
6. Repeat until the LLM produces a final text response

If the model doesn't support tool calling (e.g., certain Groq models), the system detects this automatically, disables tools, and retries without schemas.

### Token Optimization

The ContextBuilder ensures the LLM never exceeds its context window:

- **System prompt** — prepended once (no duplicate system messages)
- **Conversation history** — trimmed from the oldest messages until the estimated token count fits within budget
- **Reserve tokens** — space is reserved for the LLM's response
- **Task-specific max_tokens** — different tasks get different response length budgets (chat: 2048, planner: 4096, security: 4096)
- **Usage logging** — every API call logs `prompt_tokens`, `completion_tokens`, and `total_tokens` to the console

### Output Compression

All tool outputs pass through `OutputCompressor` before being stored in memory:

- **Binary** — replaced with a summary of byte count
- **JSON** — structure summarized (keys, item count, first-item preview)
- **HTML** — metadata extracted (title, description, header counts, links, scripts)
- **Plain text** — head/tail preview with middle truncation when exceeding the limit (default: 3000 chars)

## Requirements

- Python 3.10+
- A [Groq API key](https://console.groq.com/keys)

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Create a `.env` file in the project root with your API key:

```dotenv
GROQ_API_KEY=gsk_your-api-key-here
```

### All Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | *(required)* | Your Groq API key |
| `GROQ_MODEL` | Uses Groq default | Model identifier (e.g., `mixtral-8x7b-32768`) |
| `GROQ_BASE_URL` | Groq's API URL | Base URL for the OpenAI-compatible API |
| `GROQ_TIMEOUT` | `60` | Request timeout in seconds |
| `DEFAULT_MAX_CONTEXT_TOKENS` | `6000` | Maximum context tokens for the LLM |
| `DEFAULT_MAX_HISTORY_MESSAGES` | `20` | Max conversation history messages kept in memory |
| `DEFAULT_MAX_TOOL_OUTPUT_CHARS` | `3000` | Max characters per tool output before compression |
| `DEFAULT_MAX_FILE_SIZE` | `10000` | Max file size in characters for read operations |
| `DEFAULT_MAX_LIST_ITEMS` | `50` | Max items shown when listing directories |
| `DEFAULT_MAX_OUTPUT_LINES` | `100` | Max lines for terminal command output |
| `DEFAULT_RESERVE_RESPONSE_TOKES` | `1000` | Tokens reserved for the LLM response |

*(Note: `RESPONSE_TOKES` is a legacy spelling — both the variable and code use this form for now.)*

## Usage

### CLI Mode (default)

Run a single prompt:

```bash
python main.py "Explain dependency injection simply"
```

Or launch interactive mode:

```bash
python main.py
```

Type `exit`, `quit`, or press `Ctrl-D` to leave interactive mode.

### Web UI

Start the web server:

```bash
python main.py --web
```

Opens a FastAPI-based chat interface at **`http://localhost:8000`** with:
- `/` — HTML chat UI
- `/api/chat` — JSON API endpoint for programmatic access
- `/api/reset` — Reset conversation memory

The server runs on `0.0.0.0:8000` by default (accessible on your network).

### API Endpoints

#### `POST /api/chat`

```json
{ "message": "What files are in this project?" }
```

Response:

```json
{
  "content": "Here's what I found...",
  "model": "mixtral-8x7b-32768",
  "usage": {
    "prompt_tokens": 452,
    "completion_tokens": 128,
    "total_tokens": 580
  }
}
```

#### `POST /api/reset`

```json
{ "status": "ok", "message": "Conversation reset." }
```

## Extending

### Add a New Tool

Create a new tool class, register its operations, and add it to the registry:

```python
# app/tools/mytool.py
from app.tools.base import Tool, ToolResult, ToolOperation

class MyTool(Tool):
    name = "mytool"
    description = "Description of my custom tool."

    def my_operation(self, arg: str) -> ToolResult:
        # Your logic here
        return ToolResult(success=True, content=f"Processed: {arg}")

    def operations(self) -> list[ToolOperation]:
        return [ToolOperation(
            name=f"{self.name}.my_operation",
            description="Describe this operation for the LLM.",
            parameters={
                "type": "object",
                "properties": {
                    "arg": {"type": "string", "description": "An argument."},
                },
                "required": ["arg"],
            },
            fn=self.my_operation,
        )]

# In app/tools/__init__.py:
registry.register(MyTool())
```

### Add a New Route

1. Create a prompt template: `prompts/myroute.md`
2. Add routing logic in `app/core/pipeline/router.py`:

```python
if "myroute" in text:
    return Route(task="myroute", prompts="myroute")
```

3. *(Optional)* Add a task-specific `max_tokens` in `executor.py`.

### Add a New LLM Provider

```python
# app/core/ai/anthropic.py
from app.core.ai.base import LLMProvider

class AnthropicProvider(LLMProvider):
    # Implement generate() method

# In app/core/ai/factory.py:
_providers = {
    "groq": GroqProvider,
    "anthropic": AnthropicProvider,
}
```

## Project Structure

```
glitch-assistant/
├── main.py                     # Entry point (CLI or --web)
├── app/
│   ├── application.py          # Shared dependency injection
│   ├── agents/                 # Agent implementations
│   ├── api/                    # API layer (future)
│   ├── config/
│   │   ├── settings.py         # Environment variable config
│   │   └── prompt.py           # Prompt file loader
│   ├── core/
│   │   ├── ai/                 # LLM providers (Groq, factory)
