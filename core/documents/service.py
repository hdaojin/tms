import base64
from datetime import date
from pathlib import Path

from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from .content import prepare_content
from .renderer import render_pdf, render_slot
from .types import DocumentError, DocumentInput, DocumentRenderError, DocumentTemplate

TEMPLATES = {
    "standard": DocumentTemplate("standard", "标准文档", ("css/documents/base.css", "css/documents/standard.css")),
    "formal": DocumentTemplate("formal", "正式文档", ("css/documents/base.css", "css/documents/formal.css")),
}


def list_document_templates() -> tuple[DocumentTemplate, ...]:
    return tuple(TEMPLATES.values())


def _render_document(document: DocumentInput, *, for_pdf: bool):
    template = TEMPLATES.get(document.template_id)
    if template is None:
        raise DocumentError("未知的文档模板。")
    if document.document_date is not None and type(document.document_date) is not date:
        raise DocumentError("文档日期格式无效。")

    soup, images = prepare_content(document, for_pdf=for_pdf)
    if not for_pdf:
        urls = {
            src: f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}"
            for src, (content, mime) in images.items()
        }
        for image in soup.find_all("img"):
            image["src"] = urls[image["src"]]

    html = render_to_string(
        "documents/document.html",
        {
            "title": document.title.strip(),
            "subtitle": document.subtitle.strip(),
            "author": document.author.strip(),
            "organization": document.organization.strip(),
            "document_date": document.document_date,
            "body": mark_safe(soup.decode()),
            "template_id": template.id,
            "stylesheets": () if for_pdf else template.stylesheets,
        },
    )
    return html, template, images


def render_document_html(document: DocumentInput) -> str:
    """Return the complete HTML document for display inside a sandboxed iframe."""
    html, _, _ = _render_document(document, for_pdf=False)
    return html


def generate_document_pdf(document: DocumentInput) -> bytes:
    """Render a PDF without creating a file or retaining document data."""
    with render_slot() as lock:
        html, template, images = _render_document(document, for_pdf=True)
        styles = []
        try:
            for stylesheet in template.stylesheets:
                path = finders.find(stylesheet)
                if path is None:
                    raise FileNotFoundError(stylesheet)
                styles.append(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            raise DocumentRenderError("无法读取文档模板样式，请检查静态资源。") from exc
        return render_pdf(html, styles, images, lock=lock)
