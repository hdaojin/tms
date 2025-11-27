#!/usr/bin/env python3
"""
Concat all Python source files in a workspace into a single file.

Usage examples:
  python scripts/concat_python.py -o all_python_code.txt
  python scripts/concat_python.py -r . -o out/all_py.txt --exclude-dir .git --exclude-dir node_modules

This script uses only the Python standard library.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable, List, Set
import io
import tokenize
import ast

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

# Absolute path to this script itself, to skip including it in the output
SCRIPT_PATH = Path(__file__).resolve()


def iter_python_files(root: Path, excluded: Set[str]) -> List[Path]:
    root = root.resolve()
    py_files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # prune excluded directories (by name) and hidden directories
        dirnames[:] = [
            d
            for d in dirnames
            if d not in excluded and not d.startswith(".")
        ]
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            # Skip hidden files
            if fname.startswith("."):
                continue
            fpath = Path(dirpath) / fname
            # Skip this script itself
            try:
                if fpath.resolve() == SCRIPT_PATH:
                    continue
            except Exception:
                pass
            py_files.append(fpath)
    # Sort deterministically by relative path
    py_files.sort(key=lambda p: str(p.relative_to(root)).lower())
    return py_files


def concat_files(files: Iterable[Path], root: Path, output: Path) -> int:
    """Concatenate cleaned source; ignore files that become empty after stripping.

    Returns number of included (non-empty) files.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    files = list(files)
    included = 0
    with output.open("w", encoding="utf-8", newline="\n") as out:
        for path in files:
            try:
                with path.open("r", encoding="utf-8", errors="replace") as f:
                    src = f.read()
                no_doc = strip_docstrings(src)
                cleaned = strip_python_comments(no_doc).strip()
                cleaned = remove_blank_lines(cleaned)
            except Exception as e:
                cleaned = f"# [ERROR] Could not read {path.relative_to(root)}: {e}"
            if not cleaned:
                # Skip empty result
                continue
            if included > 0:
                # Separator without extra blank lines
                out.write("\n----\n")
            out.write(cleaned)
            included += 1
        out.write("\n")
    return included


def strip_python_comments(text: str) -> str:
    """Remove all Python comments (# ...), preserving code and strings.

    Uses tokenize to drop COMMENT tokens. Docstrings are kept (they are strings),
    which is safer unless explicitly requested otherwise.
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
        out_tokens = [tok for tok in tokens if tok.type != tokenize.COMMENT]
        return tokenize.untokenize(out_tokens)
    except Exception:
        # Fallback: drop full-line comments only
        lines = []
        for line in text.splitlines():
            if line.lstrip().startswith('#'):
                lines.append('')
            else:
                lines.append(line)
        return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def strip_docstrings(text: str) -> str:
    """Remove top-level/module, class, and function docstrings.

    Keeps formatting of remaining lines; removes full line range occupied by the docstring expression.
    If AST parsing fails, returns original text.
    """
    try:
        tree = ast.parse(text)
    except Exception:
        return text

    # Collect (start,end) line ranges to delete
    to_remove: List[tuple[int, int]] = []

    def record_doc(node):
        if not hasattr(node, 'body') or not node.body:
            return
        first = node.body[0]
        if isinstance(first, ast.Expr):
            val = getattr(first, 'value', None)
            # In modern Python (>=3.8) docstrings appear as ast.Constant with str value
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                start = first.lineno
                end = getattr(first, 'end_lineno', first.lineno)
                to_remove.append((start, end))

    # Module docstring
    record_doc(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            record_doc(node)

    if not to_remove:
        return text

    # Build set of lines to skip
    skip: Set[int] = set()
    for s, e in to_remove:
        skip.update(range(s, e + 1))

    lines = text.splitlines()
    cleaned_lines = [ln for i, ln in enumerate(lines, start=1) if i not in skip]
    return "\n".join(cleaned_lines) + ("\n" if text.endswith("\n") else "")


def remove_blank_lines(text: str) -> str:
    """Remove all blank lines (lines that are empty or whitespace only)."""
    return "\n".join(ln for ln in text.splitlines() if ln.strip() != "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Concat all Python (*.py) files into a single output file.")
    parser.add_argument("-r", "--root", type=str, default=".", help="Workspace root to scan (default: current directory)")
    parser.add_argument("-o", "--output", type=str, default="all_python_code.txt", help="Output file path (default: all_python_code.txt)")
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

    files = iter_python_files(root, excluded)
    included = concat_files(files, root, output)
    print(f"Wrote {included} non-empty files into: {output}")


if __name__ == "__main__":
    main()
