#!/usr/bin/env python3
# main.py
"""
Entry point for Glitch Assistant.

Usage:
    python main.py          # Start CLI
    python main.py --web    # Start Web GUI
"""
from __future__ import annotations

import sys


def main():
    if "--web" in sys.argv:
        from app.interfaces.web.server import run
        run()
    else:
        from app.interfaces.cli.main import run
        run()


if __name__ == "__main__":
    main()
