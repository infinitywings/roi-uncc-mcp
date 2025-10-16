#!/usr/bin/env python3
"""Command line entrypoint for the EV Setpoint MCP server."""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Enable local package imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from src.server import EVSetpointMCPServer, load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EV Setpoint MCP server")
    parser.add_argument(
        "--config",
        default=os.path.join(CURRENT_DIR, "config", "ev_mcp.yaml"),
        help="Path to YAML configuration file"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (default: INFO)"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    config = load_config(args.config)
    server = EVSetpointMCPServer(config)
    server.start()


if __name__ == "__main__":
    main()
