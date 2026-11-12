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
from core.documents.renderer import render_slot
from core.documents.sample import sample_document, topology_asset
from core.utils.markdown import render_markdown_text


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


@pytest.mark.parametrize("kind", ["animation", "mime", "invalid", "pixels", "bytes"])
def test_rejects_unsafe_image_assets(kind):
    if kind == "animation":
        buffer = BytesIO()
        first = Image.new("RGB", (8, 8), "red")
        second = Image.new("RGB", (8, 8), "blue")
        first.save(buffer, format="PNG", save_all=True, append_images=[second])
        asset = DocumentAsset(buffer.getvalue(), "image/png")
    elif kind == "pixels":
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
