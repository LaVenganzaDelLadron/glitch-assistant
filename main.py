"""Command-line entry point for Glitch Assistant."""

from __future__ import annotations

import argparse
import sys
from app.core.ai.groq import LLMError, generate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask Glitch Assistant a question.")
    parser.add_argument("prompt", nargs="*", help="Question to send to Groq.")
    return parser.parse_args()


def get_prompt(args: argparse.Namespace) -> str | None:
    if args.prompt:
        return " ".join(args.prompt).strip()

    try:
        prompt = input("You: ").strip()
    except EOFError:
        print()
        return None

    if prompt.lower() in {"exit", "quit"}:
        return None
    return prompt


def main() -> int:
    prompt = get_prompt(parse_args())
    if not prompt:
        return 0

    try:
        print(generate(prompt))
    except LLMError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
