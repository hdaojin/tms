import base64
import shutil
import subprocess
import sys
from dataclasses import replace
from io import BytesIO

import pytest
from bs4 import BeautifulSoup
from django.utils.safestring import mark_safe
from PIL import Image

from core.documents import (
    DocumentAsset,
    DocumentBusy,
    DocumentError,
    DocumentInput,
    generate_document_pdf,
    list_document_templates,
    render_document_html,
)
from core.documents.limits import MAX_CONTENT_BYTES
from core.documents.content import normalize_document_image, prepare_content
from core.documents.renderer import render_slot
from core.documents.sample import sample_document, topology_asset
from core.utils.markdown import render_markdown_text
from core.documents.markdown import render_content_markdown


@pytest.mark.parametrize(
    ("format_name", "mime"),
    [
        ("GIF", "image/gif"), ("PNG", "image/png"), ("WebP", "image/webp"),
        ("BMP", "image/bmp"), ("TIFF", "image/tiff"),
        ("AVIF", "image/avif"), ("HEIF", "image/heic"), ("ICO", "image/x-icon"),
    ],
)
def test_additional_raster_formats(format_name, mime):
    output = BytesIO()
    first = Image.new("RGB", (32, 32), "red")
    if format_name in {"GIF", "PNG", "WebP", "TIFF"}:
        first.save(output, format=format_name, save_all=True, append_images=[Image.new("RGB", first.size, "blue")])
    else:
        first.save(output, format=format_name)
    content, media_type, _ = normalize_document_image(DocumentAsset(output.getvalue(), mime), "图片")
    with Image.open(BytesIO(content)) as image:
        assert media_type == "image/png" and image.n_frames == 1
        red, green, blue = image.getpixel((0, 0))
        assert red > 220 and green < 35 and blue < 35


def test_svg_removes_active_and_external_content_from_document_asset():
    source = b'''<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" onload="alert(1)">
      <script>alert(1)</script><image href="https://example.com/a.png"/>
      <defs><linearGradient id="local"><stop offset="1" stop-color="red"/></linearGradient></defs>
      <rect width="32" height="32" style="fill:url(#local);stroke:url(https://example.com/b)"/>
    </svg>'''
    document = DocumentInput(
        title="矢量图", content="![示意图](tms-asset:vector)", assets={"vector": DocumentAsset(source, "image/svg+xml")},
    )
    _, images = prepare_content(document, for_pdf=True)
    clean, mime = images["tms-asset:vector"]
    assert mime == "image/svg+xml"
    assert b'fill="url(#local)"' in clean
    assert not any(token in clean for token in (b"example.com", b"onload", b"<script", b"<image"))
    assert "data:image/svg+xml;base64," in render_document_html(document)


@pytest.mark.parametrize("source", [
    b'<!DOCTYPE svg [<!ENTITY x "text">]><svg xmlns="http://www.w3.org/2000/svg"><text>&x;</text></svg>',
    b'<svg xmlns="http://www.w3.org/2000/svg" width="3000" height="3000"/>',
    b'<svg xmlns="http://www.w3.org/2000/svg"><linearGradient id="x" href="#x"/></svg>',
])
def test_svg_rejects_unsupported_xml_and_excessive_resources(source):
    with pytest.raises(DocumentError, match="SVG"):
        normalize_document_image(DocumentAsset(source, "image/svg+xml"), "图片")


def test_shared_content_preserves_details_and_filters_active_markup(tmp_path):
    from notes.utils import render_note_markdown

    source = """# 教学单元

<details>
<summary>操作步骤</summary>

| 命令 | 用途 |
| --- | --- |
| help | 查询帮助 |

</details>

<script>alert(1)</script>
"""
    path = tmp_path / "lesson.md"
    path.write_text(source, encoding="utf-8")
    notebook = render_note_markdown(path, "linux", tmp_path, "lesson")
    shared = render_content_markdown(source, metadata=True)
    assert notebook.html == shared.html
    exported = BeautifulSoup(render_document_html(DocumentInput(title="教学单元", content=source)), "html.parser")
    assert exported.select_one("details[open] table td").text == "help"
    assert exported.select_one("summary").text == "操作步骤"
    assert not exported.select("script")


def test_shared_markdown_keeps_asset_only_content():
    rendered = render_content_markdown("![插图](tms-asset:demo)", document_assets=True)
    assert BeautifulSoup(rendered.html, "html.parser").img["src"] == "tms-asset:demo"


def test_template_registry_and_markdown_structure():
    assert [(template.id, template.name) for template in list_document_templates()] == [
        ("standard", "标准文档"),
        ("formal", "正式文档"),
    ]
    document = sample_document()
    standard = BeautifulSoup(render_document_html(document), "html.parser")
    formal = BeautifulSoup(render_document_html(replace(document, template_id="formal")), "html.parser")
    assert standard.title.text == "网络系统管理训练报告"
    assert standard.select_one(".document-subtitle").text == "连通性验证与故障排查"
    assert standard.select_one("time")["datetime"] == "2026-11-12"
    assert standard.select_one(".document-body") == formal.select_one(".document-body")
    assert standard.select_one("thead th").text == "序号"
    assert "<latency> & packet loss" in standard.select_one("pre code").text
    assert standard.select_one("img")["src"].startswith("data:image/png;base64,")
    assert standard.select_one("link[href$='standard.css']")
    assert formal.select_one("link[href$='formal.css']")


def test_html_whitelist_and_external_links_are_inert_in_preview():
    html = render_document_html(
        DocumentInput(
            title=mark_safe("<script>metadata</script>"),
            content_format="html_fragment",
            content="""
          <script>throw 'bad'</script><style>p {color: red}</style>
          <base href="https://example.com"><iframe>hidden frame</iframe>
          <form>hidden form</form><svg><text>hidden svg</text></svg>
          <p id="start" style="color:red" class="untrusted" onclick="throw 'bad'">正文</p>
          <a href="https://example.com" rel="attachment">外部链接</a>
          <a href="java&#x09;script:alert(1)">危险链接</a>
          <a href="#start">返回正文</a>
          <table><tr><td colspan="2" rowspan="999999">表格</td></tr></table>
        """,
        )
    )
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one(".document-body")
    assert soup.title.text == "<script>metadata</script>"
    assert not body.select("script, style, base, iframe, form, svg, [style], [onclick], [rel], [class]")
    assert "hidden" not in body.text
    assert [link.get("href") for link in body.select("a")] == [None, None, "about:srcdoc#start"]
    assert body.select_one("td").attrs == {"colspan": "2"}


@pytest.mark.parametrize(
    "source",
    [
        "file:///etc/passwd",
        "http://127.0.0.1/image.png",
        "http://169.254.169.254/latest/meta-data",
        "https://localhost/redirect",
        "//localhost/a.png",
        "\\\\server\\share\\a.png",
        "/etc/passwd",
        "./local.png",
        "data:image/png;base64,AAAA",
        "tms-asset://topology",
        "tms-asset:missing",
    ],
)
def test_rejects_unapproved_image_sources(source):
    with pytest.raises(DocumentError, match="图片"):
        render_document_html(
            DocumentInput(
                title="文档",
                content=f'<p>正文<img src="{source}" alt="图片"></p>',
                content_format="html_fragment",
                assets={"topology": topology_asset()},
            )
        )


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"title": " "}, "标题"),
        ({"content": ""}, "正文"),
        ({"content": "<script>bad</script>"}, "清理后"),
        ({"content": "测" * (MAX_CONTENT_BYTES // 3 + 1)}, "1 MiB"),
        ({"template_id": "../base"}, "模板"),
        ({"content_format": "xml"}, "格式"),
        ({"content": "<p>文</p>" * 20_001}, "元素"),
        ({"content": "<blockquote>" * 50 + "文" + "</blockquote>" * 50}, "层级"),
    ],
)
def test_invalid_documents_fail_with_actionable_errors(overrides, message):
    document = DocumentInput(title="文档", content="<p>正文</p>", content_format="html_fragment")
    with pytest.raises(DocumentError, match=message):
        render_document_html(replace(document, **overrides))


def test_markdown_strict_errors_preserve_previous_callers(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("parse failure")

    monkeypatch.setattr("core.utils.markdown.markdown2.markdown", fail)
    assert render_markdown_text("旧调用").html == ""
    with pytest.raises(DocumentError, match="Markdown"):
        render_document_html(DocumentInput(title="文档", content="正文"))


def _render_asset(asset):
    document = DocumentInput(title="文档", content="![图](tms-asset:demo)", assets={"demo": asset})
    return BeautifulSoup(render_document_html(document), "html.parser").img["src"]


def test_orients_jpeg_and_strips_metadata():
    source = Image.new("RGB", (12, 24))
    exif = source.getexif()
    exif[274] = 6
    exif[270] = "private metadata"
    buffer = BytesIO()
    source.save(buffer, format="JPEG", exif=exif)
    src = _render_asset(DocumentAsset(buffer.getvalue(), "image/jpeg"))
    with Image.open(BytesIO(base64.b64decode(src.split(",", 1)[1]))) as output:
        assert output.size == (24, 12)
        assert not output.getexif()


@pytest.mark.parametrize("kind", ["mime", "invalid", "pixels", "bytes"])
def test_rejects_unsafe_image_assets(kind):
    if kind == "pixels":
        buffer = BytesIO()
        Image.new("L", (3000, 3000)).save(buffer, format="PNG")
        asset = DocumentAsset(buffer.getvalue(), "image/png")
    else:
        asset = {
            "mime": DocumentAsset(topology_asset().content, "image/webp"),
            "invalid": DocumentAsset(b"invalid", "image/png"),
            "bytes": DocumentAsset(b"x" * (5 * 1024 * 1024 + 1), "image/png"),
        }[kind]
    with pytest.raises(DocumentError, match="图片"):
        _render_asset(asset)


@pytest.mark.document_pdf_native
@pytest.mark.skipif(sys.platform != "linux", reason="PDF rendering requires Linux and Noto CJK")
def test_renders_svg_in_pdf():
    source = b'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="80"><text y="35">SVG proof</text></svg>'
    document = DocumentInput(
        title="矢量图", content="![示意图](tms-asset:vector)", assets={"vector": DocumentAsset(source, "image/svg+xml")},
    )
    from pypdf import PdfReader

    assert "SVG proof" in PdfReader(BytesIO(generate_document_pdf(document))).pages[0].extract_text()


@pytest.mark.document_pdf_native
@pytest.mark.skipif(sys.platform != "linux", reason="PDF rendering and instance locks require Linux")
def test_pdf_slot_rejects_concurrent_render_and_reopens():
    with render_slot():
        with pytest.raises(DocumentBusy):
            generate_document_pdf(sample_document())
    with render_slot():
        pass


@pytest.mark.document_pdf_native
@pytest.mark.skipif(sys.platform != "linux", reason="PDF rendering requires Linux and Noto CJK")
def test_renderer_fails_closed_on_unregistered_resources():
    from core.documents.worker import render_payload

    for source in ("file:///etc/passwd", "http://127.0.0.1/a.png", "http://169.254.169.254/latest/meta-data"):
        with pytest.raises(ValueError, match="Unexpected PDF resource"):
            render_payload({"html": f'<p>正文</p><img src="{source}">', "styles": [], "images": {}})


@pytest.mark.document_pdf_native
@pytest.mark.skipif(sys.platform != "linux", reason="PDF rendering requires Linux and Noto CJK")
@pytest.mark.parametrize("template_id", ["standard", "formal"])
def test_renders_chinese_multipage_pdf_with_repeated_header(template_id, tmp_path):
    document = replace(sample_document(template_id), subtitle="包含表格、代码与插图")
    pdf = generate_document_pdf(document)
    assert pdf.startswith(b"%PDF-")
    if shutil.which("pdftotext"):
        sample = tmp_path / f"{template_id}.pdf"
        sample.write_bytes(pdf)
        text = subprocess.check_output(["pdftotext", "-enc", "UTF-8", sample, "-"]).decode("utf-8")
        pages = ["".join(page.split()) for page in text.split("\f") if page.strip()]
        assert len(pages) >= 2
        assert "网络系统管理训练报告" in pages[0]
        assert sum("序号" in page for page in pages) >= 2
        assert "完成全部检查项" in pages[-1]
        assert "第1页" in pages[0]
        info = subprocess.check_output(["pdfinfo", sample])
        assert b"pts (A4)" in info
        images = subprocess.check_output(["pdfimages", "-list", sample]).decode("ascii")
        assert any(line.split()[3:5] == ["840", "200"] for line in images.splitlines())
