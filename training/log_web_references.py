import http.client
import ipaddress
import socket
from urllib.parse import quote, urlsplit

from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError

MAX_LINKS = 3
MAX_PAGE_BYTES = 512 * 1024
MAX_EXCERPT = 4000
TIMEOUT = 3
GLOBAL_UNICAST_V6 = ipaddress.IPv6Network("2000::/3")


def read_page(url):
    parts = urlsplit(url)
    secure = parts.scheme == "https"
    port = 443 if secure else 80
    host = parts.hostname
    if (
        parts.scheme not in {"http", "https"}
        or not host
        or parts.username is not None
        or parts.port not in {None, port}
    ):
        raise ValueError
    host = host.encode("idna").decode("ascii")
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    for _, _, _, _, address in addresses:
        ip = ipaddress.ip_address(address[0])
        if isinstance(ip, ipaddress.IPv6Address):
            if ip not in GLOBAL_UNICAST_V6 or ip.sixtofour or ip.teredo or ip.scope_id:
                raise ValueError
        if not ip.is_global or ip.is_multicast:
            raise ValueError
    if not addresses:
        raise ValueError

    family, kind, protocol, _, address = addresses[0]
    connection_class = http.client.HTTPSConnection if secure else http.client.HTTPConnection
    connection = connection_class(host, port, timeout=TIMEOUT)

    # Connect to the vetted address while keeping the hostname for Host, SNI and TLS validation.
    def connect_to_address(*args):
        sock = socket.socket(family, kind, protocol)
        try:
            sock.settimeout(TIMEOUT)
            sock.connect(address)
        except OSError:
            sock.close()
            raise
        return sock

    connection._create_connection = connect_to_address
    try:
        path = quote(parts.path or "/", safe="/%:@!$&'()*+,;=")
        if parts.query:
            path += "?" + quote(parts.query, safe="/?%:@!$&'()*+,;=")
        connection.request("GET", path)
        with connection.getresponse() as response:
            mime = response.headers.get_content_type()
            if response.status != 200 or mime not in {"text/html", "text/plain", "application/xhtml+xml"}:
                raise ValueError
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError
            body = response.read(MAX_PAGE_BYTES + 1)
            charset = response.headers.get_content_charset()
    finally:
        connection.close()
    if len(body) > MAX_PAGE_BYTES:
        raise ValueError
    if mime == "text/plain":
        return body.decode(charset or "utf-8", errors="replace").strip()[:MAX_EXCERPT]
    page = BeautifulSoup(body, "html.parser", from_encoding=charset)
    content = page.find("main") or page.find("article") or page.body or page
    for node in content.select("script, style, template, noscript, nav, footer"):
        node.decompose()
    return content.get_text("\n", strip=True)[:MAX_EXCERPT]


def fetch_reference_pages(references):
    excerpts = []
    for index, url in enumerate(references.splitlines(), 1):
        try:
            excerpt = read_page(url)
            if not excerpt:
                raise ValueError
        except (OSError, http.client.HTTPException, ValueError, LookupError):
            raise ValidationError(
                f"无法读取第 {index} 个参考链接。请检查公开页面地址，或将相关文字粘贴到补充说明。"
            ) from None
        excerpts.append({"链接": url, "正文摘录": excerpt})
    return excerpts
