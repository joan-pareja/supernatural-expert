"""Validate the wrap-up skill's hard commit-title rules."""

from __future__ import annotations

import argparse
import re

MAX_TITLE_LENGTH = 70
TITLE_PATTERN = re.compile(
    r"^(?:feat|fix|refactor|perf|docs|test|build|ci|style|chore|revert)"
    r"(?:\([a-z0-9][a-z0-9._/-]*\))?!?: [a-z0-9](?:.*[^.])?$"
)


def validate_title(title: str) -> list[str]:
    """Return human-readable validation failures for a commit title."""
    failures: list[str] = []
    if len(title) > MAX_TITLE_LENGTH:
        failures.append(
            f"title is {len(title)} characters; maximum is {MAX_TITLE_LENGTH}"
        )
    if "\n" in title or "\r" in title:
        failures.append("title must be exactly one physical line")
    if not TITLE_PATTERN.fullmatch(title):
        failures.append(
            "title must use Conventional Commit syntax, start its summary in "
            "lowercase, and omit the final period"
        )
    return failures


def main() -> int:
    """Validate the supplied title and return a shell-friendly exit code."""
    parser = argparse.ArgumentParser()
    parser.add_argument("title")
    args = parser.parse_args()

    failures = validate_title(args.title)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1

    print(f"OK: {len(args.title)}/{MAX_TITLE_LENGTH} characters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
