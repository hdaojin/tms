from dataclasses import dataclass
from typing import Any
from collections.abc import Callable, Sequence

import markdown2


DEFAULT_MARKDOWN_EXTRAS: list[str] = [
    "code-friendly",           # Disable _ and __ for em and strong
    "cuddle-lists",            # Allow lists to be cuddled to the preceding paragraph
    "fenced-code-blocks",      # Support for ``` code blocks
    "footnotes",               # Support for footnotes
    "header-ids",              # Adds "id" attributes to headers
    "highlightjs-lang",        # Highlight code blocks with highlight.js language classes
    "metadata",                # Support for YAML metadata at the top of the file
    "nofollow",                # Add rel="nofollow" to all <a> tags with an href.
    "numbering",               # Create counters to number tables, figures, equations and graphs
    "pyshell",                 # Treats unindented Python interactive shell sessions as <code> blocks. 
    "smarty-pants",            # Fancy quote, em-dash and ellipsis handling similar to http://daringfireball.net/projects/smartypants/. 
    "tag-friendly",            # Convert #tags into linksRequires atx style headers to have a space between the # and the header text. Useful for applications that require twitter style tags to pass through the parser.
    "tables",                  # Support for tables
    # "target-blank-links",      # Add target="_blank" to all <a> tags with an href.
    "toc",                     # Table of contents generation
    "task_list",               # Support for GitHub-style task lists
    "break-on-newline",        # Treat single newlines as line breaks
    "admonitions",             # Support for admonition blocks (note, warning, etc.)
]


@dataclass
class RenderedMarkdown:
    """A reusable container for rendered Markdown output."""

    html: str
    meta: dict[str, Any]
    toc: str | None 


def _lower_meta_keys(meta: dict[str, Any]) -> dict[str, Any]:
    return {str(key).lower(): value for key, value in meta.items()}


def render_markdown_text(
    text: str,
    *, # Enforce keyword arguments
    extensions: Sequence[str] = DEFAULT_MARKDOWN_EXTRAS,
    html_postprocessor: Callable[[str], str] | None = None,
    lower_meta_keys: bool = True,
) -> RenderedMarkdown:
    """Render Markdown text into HTML."""

    try:
        rendered_html = markdown2.markdown(text, extras=list(extensions))
        meta_data: dict[str, Any] = rendered_html.metadata or {}
        toc_content: str | None = rendered_html.toc_html
        if lower_meta_keys:
            meta_data = _lower_meta_keys(meta_data)

    except Exception:  
        rendered_html = ""
        meta_data = {}
        toc_content = None

    if html_postprocessor is not None:
        rendered_html = html_postprocessor(rendered_html)
    return RenderedMarkdown(
        html=rendered_html,
        meta=meta_data,
        toc=toc_content,
    )

