# app/interfaces/web/server.py
"""
FastAPI-based Web GUI for Glitch Assistant.

Launched via `python main.py --web` or standalone with `uvicorn`.
Provides a chat UI at / and a JSON API at /api/chat.
"""
from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.application import create_pipeline
from app.core.memory.conversation import ConversationMemory
from app.config.prompt import PromptLoader

app = FastAPI(title="Glitch Assistant")

# ── Shared pipeline instance (lazy init) ──────────────────────────────────
_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = create_pipeline()
    return _pipeline


# ── Static files & templates ─────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE / "static"
TEMPLATES_DIR = HERE / "templates"

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── API models ───────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    content: str
    model: str
    usage: dict | None = None


# ── Routes ───────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the chat UI."""
    index_path = TEMPLATES_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>Chat UI not found</h1>", status_code=404)
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.post("/api/chat")
async def chat(request: ChatRequest) -> JSONResponse:
    """Process a chat message and return the assistant's response."""
    try:
        pipeline = get_pipeline()
        response = pipeline.run(request.message)

        return JSONResponse(
            ChatResponse(
                content=response.content,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                } if response.usage else None,
            ).model_dump(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reset")
async def reset_conversation() -> JSONResponse:
    """Reset the conversation memory (start fresh)."""
    pipeline = get_pipeline()
    pipeline.context.conversation = ConversationMemory()
    pipeline.context.conversation.add_system(
        PromptLoader.load("system"),
    )
    return JSONResponse({"status": "ok", "message": "Conversation reset."})


# ── Entry point ──────────────────────────────────────────────────────────
def run(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Launch the web server."""
    import uvicorn

    print(f"🌐 Web UI: http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run()
