"""Entry point — interactive REPL and single-prompt modes."""

from __future__ import annotations
import logging
import sys
from app.core.pipeline.pipeline import run

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s %(message)s",
    stream=sys.stderr,
)


def _repl() -> None:
    """Run the interactive read-eval-print loop."""
    print("Glitch Assistant — type 'exit' to quit.\n")
    while True:
        try:
            user_input = input("Chat: ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        normalized = user_input.strip().lower()
        if normalized in ("exit", "quit"):
            break

        try:
            response = run(user_input)
            print(f"AI: {response}\n")
        except Exception as exc:
            logging.getLogger(__name__).exception("Unhandled error")
            print(f"AI: Sorry, something went wrong — {exc}\n")


def main() -> None:
    """Dispatch to REPL or single-shot mode based on CLI arguments."""
    if len(sys.argv) > 1:
        # Single-shot: python main.py "your prompt"
        prompt = " ".join(sys.argv[1:])
        try:
            response = run(prompt)
            print(response)
        except Exception as exc:
            logging.getLogger(__name__).exception("Unhandled error")
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        _repl()


if __name__ == "__main__":
    main()
