#!/usr/bin/env python3
"""Validate that a Codex /goal objective fits the TUI objective limit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


DEFAULT_MAX_CHARS = 3_999
TARGET_CHARS = DEFAULT_MAX_CHARS


def objective_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if text.startswith("/goal"):
        rest = text[len("/goal") :]
        if rest.startswith((" ", "\n", "\t")):
            return rest.strip()
    return text


def read_input(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    return sys.stdin.read()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Codex /goal objective is under the character limit."
    )
    parser.add_argument("path", nargs="?", help="File containing the /goal command or objective.")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=f"Hard maximum objective characters. Default: {DEFAULT_MAX_CHARS}.",
    )
    parser.add_argument(
        "--target-chars",
        type=int,
        default=TARGET_CHARS,
        help=f"Recommended target objective characters. Default: {TARGET_CHARS}.",
    )
    parser.add_argument(
        "--strict-target",
        action="store_true",
        help="Exit non-zero when objective characters exceed --target-chars.",
    )
    args = parser.parse_args()

    objective = objective_text(read_input(args.path))
    count = len(objective)
    print(f"objective_chars={count}")
    print(f"target_chars={args.target_chars}")
    print(f"max_chars={args.max_chars}")
    if count > args.max_chars:
        print("error=objective exceeds Codex /goal character limit", file=sys.stderr)
        return 1
    if count > args.target_chars:
        print("warning=objective passes hard limit but exceeds target", file=sys.stderr)
        if args.strict_target:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
