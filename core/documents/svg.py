import math
import re

from lxml import etree

from .limits import MAX_HTML_DEPTH, MAX_HTML_NODES, MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS
from .types import DocumentError

SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
SVG_MIME = "image/svg+xml"
GRADIENTS = {"linearGradient", "radialGradient"}
ELEMENTS = {
    "svg", "g", "defs", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
    "text", "tspan", "title", "desc", "stop", *GRADIENTS,
}
ATTRIBUTES = set("""
    id width height viewBox preserveAspectRatio x y dx dy x1 y1 x2 y2 cx cy r rx ry fx fy fr d points
    transform gradientUnits gradientTransform spreadMethod offset
""".split())
PRESENTATION = set("""
    color fill fill-opacity fill-rule opacity stroke stroke-width stroke-opacity stroke-linecap
    stroke-linejoin stroke-miterlimit stroke-dasharray stroke-dashoffset stop-color stop-opacity
    font-family font-size font-style font-weight text-anchor dominant-baseline visibility display
""".split())
LOCAL_ID = r"[A-Za-z_][\w.-]*"
PAINT_REFERENCE = re.compile(rf"url\(#({LOCAL_ID})\)", re.ASCII)
LENGTH = re.compile(r"([0-9]+(?:\.[0-9]*)?|\.[0-9]+)(px|pt|pc|in|cm|mm|q)?", re.IGNORECASE)
UNIT_SCALE = {"px": 1, "pt": 96 / 72, "pc": 16, "in": 96, "cm": 96 / 2.54, "mm": 96 / 25.4, "q": 96 / 101.6}


def _dimension(value, fallback):
    if value is None:
        return fallback
    if value.strip() == "100%":
        return fallback
    match = LENGTH.fullmatch(value.strip())
    if not match:
        raise ValueError
    return float(match[1]) * UNIT_SCALE[(match[2] or "px").lower()]


def _pixels(root):
    view_box = root.get("viewBox")
    fallback = (300, 150)
    if view_box:
        bounds = [float(part) for part in re.split(r"[ ,\t\r\n]+", view_box.strip())]
        if not all(math.isfinite(part) for part in bounds):
            raise ValueError
        _, _, width, height = bounds
        fallback = (width, height)
    width = _dimension(root.get("width"), fallback[0])
    height = _dimension(root.get("height"), fallback[1])
    if any(not math.isfinite(size) or size <= 0 or size > MAX_IMAGE_PIXELS for size in (*fallback, width, height)):
        raise ValueError
    return math.ceil(width) * math.ceil(height)


def _presentation(name, value):
    if name in {"fill", "stroke"} and PAINT_REFERENCE.fullmatch(value):
        return value
    # Simple CSS values only. Block escapes, functions that load resources, and rule syntax.
    if re.fullmatch(r"[\w\s.,%#'\x22+()\-]+", value) and "url" not in value.lower():
        return value
    return None


def _copy_element(node, destination):
    for attr, value in node.attrib.items():
        value = value.strip()
        if attr in ATTRIBUTES:
            destination.set(attr, value)
        elif attr in PRESENTATION and (safe := _presentation(attr, value)):
            destination.set(attr, safe)
    for declaration in node.get("style", "").split(";"):
        name, _, value = declaration.partition(":")
        name, value = name.strip().lower(), value.strip()
        if name in PRESENTATION and (safe := _presentation(name, value)):
            destination.set(name, safe)
    destination.text, destination.tail = node.text, node.tail


def normalize_svg(content, image_id):
    try:
        if len(content) > MAX_IMAGE_BYTES:
            raise ValueError
        root = etree.fromstring(content, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        if root.tag != f"{{{SVG}}}svg" or root.getroottree().docinfo.doctype:
            raise ValueError
        pixels = _pixels(root)
        if pixels > MAX_IMAGE_PIXELS:
            raise ValueError

        output = etree.Element(f"{{{SVG}}}svg", nsmap={None: SVG, "xlink": XLINK})
        _copy_element(root, output)
        queue = [(root, output, 1)]
        gradients = {}
        references = {}
        ids = {output.get("id")} if output.get("id") else set()
        nodes = 1
        while queue:
            node, target, depth = queue.pop()
            for child in node:
                if not isinstance(child.tag, str) or not child.tag.startswith(f"{{{SVG}}}"):
                    continue
                name = etree.QName(child).localname
                if name not in ELEMENTS or name == "svg":
                    continue
                if depth >= MAX_HTML_DEPTH:
                    raise ValueError
                nodes += 1
                if nodes > MAX_HTML_NODES:
                    raise ValueError
                element = etree.SubElement(target, child.tag)
                _copy_element(child, element)
                queue.append((child, element, depth + 1))
                key = element.get("id")
                if key:
                    if key in ids:
                        raise ValueError
                    ids.add(key)
                if name in GRADIENTS and key:
                    gradients[key] = element
                    href = child.get("href") or child.get(f"{{{XLINK}}}href")
                    if href and re.fullmatch(rf"#{LOCAL_ID}", href, re.ASCII):
                        references[key] = href[1:]

        for key, ref in references.items():
            chain = {key}
            next_ref = ref
            while next_ref in references:
                if next_ref in chain or len(chain) >= MAX_HTML_DEPTH:
                    raise ValueError
                chain.add(next_ref)
                next_ref = references[next_ref]
            if ref in gradients:
                gradients[key].set(f"{{{XLINK}}}href", f"#{ref}")
        sanitized = etree.tostring(output, encoding="utf-8")
        if len(sanitized) > MAX_IMAGE_BYTES:
            raise ValueError
    except (etree.LxmlError, ValueError, OverflowError) as exc:
        raise DocumentError(f"图片「{image_id}」的 SVG 无法安全处理或尺寸超过限制。") from exc
    return sanitized, SVG_MIME, pixels
