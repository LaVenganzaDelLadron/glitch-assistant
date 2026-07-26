# app/interfaces/cli/main.py
"""
Command-Line Interface for Glitch Assistant.

This is the original CLI loop, refactored to use the shared
application bootstrap from app/application.py.
"""
from __future__ import annotations

from app.application import create_pipeline


def run() -> None:
    """Run the interactive CLI loop."""
    pipeline = create_pipeline()

    while True:
        print("\n\n")
        prompt = input("You: ")

        if prompt == "exit":
            break

        response = pipeline.run(prompt)
        print("Content: ", response.content)


if __name__ == "__main__":
    run()
