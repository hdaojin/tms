from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class DocumentAsset:
    content: bytes
    media_type: Literal["image/png", "image/jpeg", "image/webp"]


@dataclass(frozen=True)
class DocumentInput:
    title: str
    content: str
    content_format: Literal["markdown", "html_fragment"] = "markdown"
    template_id: str = "standard"
    subtitle: str = ""
    author: str = ""
    organization: str = ""
    document_date: date | None = None
    assets: Mapping[str, DocumentAsset] = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentTemplate:
    id: str
    name: str
    stylesheets: tuple[str, ...]


class DocumentError(ValueError):
    """Invalid document input."""


class DocumentRenderError(RuntimeError):
    """PDF rendering failed or is unavailable."""


class DocumentBusy(DocumentRenderError):
    """The instance is already rendering another PDF."""
