#!/usr/bin/env python3
"""Convenience entrypoint for running the server without installing the package."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from llm_grid_eval.server import main


if __name__ == "__main__":
    main()

