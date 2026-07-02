#!/usr/bin/env python3
"""Validate basic static app wiring without external dependencies."""

from __future__ import annotations

import re
import sys
from pathlib import Path


INDEX_PATH = Path("index.html")
STYLE_PATH = Path("style.css")
APP_PATH = Path("app.js")


def main() -> int:
    errors = [
        *validate_index(INDEX_PATH),
        *validate_css(STYLE_PATH),
        *validate_app(APP_PATH),
    ]
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Validated static app wiring.")
    return 0


def validate_index(path: Path) -> list[str]:
    """Validate index.html includes required static app references."""

    errors: list[str] = []
    content = read(path)
    required_snippets = [
        '<meta name="viewport"',
        '<link rel="stylesheet" href="./style.css">',
        '<script type="module" src="./app.js"></script>',
        'id="start-button"',
        'id="quiz-panel"',
        'id="result-list"',
        'id="error-panel"',
    ]
    for snippet in required_snippets:
        if snippet not in content:
            errors.append(f"{path}: missing {snippet}")

    if not re.search(r"<html\s+lang=\"ja\"", content):
        errors.append(f"{path}: html lang must be ja.")
    if "<title>" not in content or "</title>" not in content:
        errors.append(f"{path}: title is required.")
    return errors


def validate_css(path: Path) -> list[str]:
    """Run a tiny CSS sanity check."""

    content = read(path)
    errors: list[str] = []
    if content.count("{") != content.count("}"):
        errors.append(f"{path}: unbalanced CSS braces.")
    for required_selector in [".app-shell", ".answer-button", ".result-card", ".is-hidden"]:
        if required_selector not in content:
            errors.append(f"{path}: missing required selector {required_selector}.")
    return errors


def validate_app(path: Path) -> list[str]:
    """Validate key app.js wiring."""

    content = read(path)
    errors: list[str] = []
    required_snippets = [
        'const DATA_URL = "./products.json";',
        "function scoreProduct(",
        "function recommendProducts(",
        "function getRecommendableProducts(",
        "探しているのはドリップバッグですか？",
    ]
    for snippet in required_snippets:
        if snippet not in content:
            errors.append(f"{path}: missing {snippet}")
    return errors


def read(path: Path) -> str:
    """Read a text file."""

    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
