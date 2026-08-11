from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


SPACE_RE = re.compile(r" +")
TRAILING_PAREN_RE = re.compile(
    r"^(?P<base>.*?)(?:（(?P<content_full>[^()（）]+)）|\((?P<content_half>[^()（）]+)\))\s*$"
)


def normalize_display_text(value: object) -> str:
    """清理显示文本，同时保留有意义的标点和大小写。"""

    normalized = unicodedata.normalize("NFC", str(value or ""))
    chars: list[str] = []
    for char in normalized:
        if char.isspace():
            chars.append(" ")
            continue
        if unicodedata.category(char) in {"Cc", "Cf"}:
            continue
        chars.append(char)
    return SPACE_RE.sub(" ", "".join(chars)).strip()


def english_comparison_key(value: object) -> str:
    return normalize_display_text(value).casefold()


def normalized_answer(value: object, *, english: bool) -> str:
    text = normalize_display_text(value)
    return text.casefold() if english else text


def unique_normalized(values: Iterable[object], *, english: bool) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = normalize_display_text(value)
        key = normalized_answer(text, english=english)
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def generated_chinese_alias(translation: object, english_term: object, acronym: object = "") -> str:
    """仅移除等于英文词条或缩略词的末尾括注。"""

    translation_text = normalize_display_text(translation)
    match = TRAILING_PAREN_RE.fullmatch(translation_text)
    if not match:
        return ""
    content_key = english_comparison_key(match.group("content_full") or match.group("content_half"))
    accepted_keys = {english_comparison_key(english_term), english_comparison_key(acronym)} - {""}
    if content_key not in accepted_keys:
        return ""
    return normalize_display_text(match.group("base"))
