#!/usr/bin/env python3
"""
Concat all HTML files in a workspace into a single file.

Rules (mirrors the Python concat script behavior):
- Recursively scan from a root (default '.')
- Exclude common dirs by name (e.g., .git, __pycache__, node_modules, migrations, static, media, dist, build, logs, env, .env, venv, .venv)
- Remove HTML comments <!-- ... --> (multi-line supported)
- Remove all blank lines
- Skip files that become empty after cleaning
- Between files, insert exactly one line '----' (no extra blank lines around)

Usage examples:
  python scripts/concat_html.py -o all_html_code.txt
  python scripts/concat_html.py -r . -o out/all_html.txt --exclude-dir .git --exclude-dir node_modules

This script uses only the Python standard library.
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Iterable, List, Set

DEFAULT_EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "node_modules",
    "migrations",
    "static",
    "media",
    "dist",
    "build",
    "logs",
    "env",
    ".env",
    "venv",
    ".venv",
}

SCRIPT_PATH = Path(__file__).resolve()


def iter_html_files(root: Path, excluded: Set[str]) -> List[Path]:
    root = root.resolve()
    html_files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in excluded and not d.startswith('.')
        ]
        for fname in filenames:
            # include .html and .htm
            if not (fname.lower().endswith('.html') or fname.lower().endswith('.htm')):
                continue
            if fname.startswith('.'):
                continue
            fpath = Path(dirpath) / fname
            # Skip this script if placed with .html extension accidentally
            try:
                if fpath.resolve() == SCRIPT_PATH:
                    continue
            except Exception:
                pass
            html_files.append(fpath)
    html_files.sort(key=lambda p: str(p.relative_to(root)).lower())
    return html_files


_HTML_AND_TEMPLATE_COMMENT_RE = re.compile(r"<!--.*?-->|{#.*?#}", re.S)


def strip_html_comments(text: str) -> str:
    """Remove HTML comments <!-- ... -->, Django template comments {# ... #},
    and lines that start with // (e.g. JS-style single-line comments).
    """
    # First remove block-style (HTML + template) comments.
    cleaned = _HTML_AND_TEMPLATE_COMMENT_RE.sub("", text)
    # Remove lines starting with // (after optional whitespace)
    lines: List[str] = []
    for line in cleaned.splitlines():
        if line.lstrip().startswith('//'):
            continue
        lines.append(line)
    return "\n".join(lines) + ("\n" if cleaned.endswith("\n") else "")


def remove_blank_lines(text: str) -> str:
    """Remove all blank lines (lines that are empty or whitespace only)."""
    return "\n".join(ln for ln in text.splitlines() if ln.strip() != "")


def concat_files(files: Iterable[Path], root: Path, output: Path) -> int:
    """Concatenate cleaned HTML; ignore files that become empty after stripping.

    Returns the number of included (non-empty) files.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    files = list(files)
    included = 0
    with output.open("w", encoding="utf-8", newline="\n") as out:
        for path in files:
            try:
                with path.open("r", encoding="utf-8", errors="replace") as f:
                    src = f.read()
                cleaned = strip_html_comments(src)
                cleaned = remove_blank_lines(cleaned.strip())
            except Exception as e:
                cleaned = f"<!-- [ERROR] Could not read {path.relative_to(root)}: {e} -->"
                # Removing comments will drop the whole line; keep as plain text instead
                cleaned = cleaned
            if not cleaned:
                continue
            if included > 0:
                out.write("\n----\n")
            out.write(cleaned)
            included += 1
        out.write("\n")
    return included


def main() -> None:
    parser = argparse.ArgumentParser(description="Concat all HTML (*.html, *.htm) files into a single output file.")
    parser.add_argument("-r", "--root", type=str, default=".", help="Workspace root to scan (default: current directory)")
    parser.add_argument("-o", "--output", type=str, default="all_html_code.txt", help="Output file path (default: all_html_code.txt)")
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory name to exclude (can be provided multiple times). Exclusion is by directory name, not path.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = Path(args.output).resolve()

    excluded = set(DEFAULT_EXCLUDED_DIRS)
    if args.exclude_dir:
        excluded.update(args.exclude_dir)

    files = iter_html_files(root, excluded)
    included = concat_files(files, root, output)
    print(f"Wrote {included} non-empty HTML files into: {output}")


if __name__ == "__main__":
    main()
