"""Isolated text extraction for explicitly uploaded training-log references."""

import sys
from io import BytesIO
from zipfile import ZipFile

from lxml import etree
from pypdf import PdfReader

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TEXT = 12000
WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_docx(source):
    with ZipFile(source) as archive:
        entry = archive.getinfo("word/document.xml")
        if entry.file_size > 4 * MAX_FILE_BYTES:
            raise ValueError
        root = etree.fromstring(archive.read(entry), parser=etree.XMLParser(resolve_entities=False, no_network=True))
        paragraphs = ("".join(part.text or "" for part in node.iter(f"{WORD}t")) for node in root.iter(f"{WORD}p"))
        return "\n".join(paragraphs)


def extract_pdf(source):
    pdf = PdfReader(source)
    if pdf.is_encrypted:
        raise ValueError
    chunks = []
    size = 0
    for page in pdf.pages[:40]:
        text = page.extract_text()
        chunks.append(text)
        size += len(text)
        if size >= MAX_TEXT:
            break
    return "\n".join(chunks)


def main():
    if sys.platform == "linux":
        import resource

        limit = 512 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    try:
        content = sys.stdin.buffer.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            return 1
        extractor = {"docx": extract_docx, "pdf": extract_pdf}[sys.argv[1]]
        text = extractor(BytesIO(content)).strip()
        sys.stdout.buffer.write(text[:MAX_TEXT].encode("utf-8", errors="replace"))
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
