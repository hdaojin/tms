import re

import nh3


_ALLOWED_CLASSES = {
    "pre": {"mermaid-pre"},
    "div": {"mermaid", "collapse-content", "admonition", "footnotes", "codehilite", "highlight"},
    "aside": {"admonition"},
    "input": {"task-list-item-checkbox"},
    "details": {"note-details", "collapse", "collapse-arrow", "border", "border-base-300", "bg-base-100"},
    "summary": {"collapse-title", "font-semibold"},
    "p": {"admonition-title"},
    "a": {"footnote-ref", "footnoteBackLink"},
}
_ADMONITION_KINDS = {"note", "warning", "tip", "important", "caution", "danger", "attention", "hint", "seealso"}


def _filter_class(tag: str, name: str, value: str) -> str | None:
    if name != "class":
        return value
    allowed = _ALLOWED_CLASSES.get(tag, set())
    if tag in {"aside", "div"} and "admonition" in value.split():
        allowed = allowed | _ADMONITION_KINDS
    classes = [
        token for token in value.split()
        if token in allowed
        or (tag in {"code", "pre"} and re.fullmatch(r"(?:language|lang)-[\w+-]+", token, re.ASCII))
        or (tag == "span" and re.fullmatch(r"[a-z][a-z0-9]{0,4}", token, re.ASCII))
    ]
    return " ".join(classes) or None


NOTE_HTML_CLEANER = nh3.Cleaner(
    tags={
        "a", "abbr", "aside", "b", "blockquote", "br", "caption", "code", "dd", "del", "details", "div", "dl", "dt",
        "em", "figure", "figcaption", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "kbd",
        "li", "mark", "ol", "p", "pre", "s", "samp", "small", "span", "strong", "sub", "summary", "sup",
        "table", "tbody", "td", "th", "thead", "tfoot", "tr", "ul", "var", "input",
    },
    clean_content_tags={"script", "style", "iframe", "object", "svg", "math", "template", "form"},
    attributes={
        "*": {"class", "title"},
        "a": {"href"},
        "img": {"src", "alt", "width", "height"},
        "details": {"open"},
        "div": {"data-mermaid-diagram", "id"},
        **{heading: {"id"} for heading in ("h1", "h2", "h3", "h4", "h5", "h6")},
        "ol": {"start"},
        "li": {"id"},
        "sup": {"id"},
        "td": {"colspan", "rowspan"},
        "th": {"scope", "colspan", "rowspan"},
        "input": {"checked"},
    },
    set_tag_attribute_values={"input": {"type": "checkbox", "disabled": ""}},
    attribute_filter=_filter_class,
    url_schemes={"http", "https", "mailto", "tel", "ftp"},
    link_rel="nofollow noopener noreferrer",
)
