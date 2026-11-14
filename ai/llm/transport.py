import http.client
import ipaddress
import socket
from time import monotonic
from threading import Lock
from urllib.parse import urlsplit

import httpx
from django.conf import settings
from django.views.decorators.debug import sensitive_variables

from ai.providers import ProviderError


def resolve_target(scheme, host, port):
    trusted = (scheme, host, port) in {
        (url.scheme, url.hostname, url.port or (443 if url.scheme == "https" else 80))
        for value in settings.AI_TRUSTED_ENDPOINTS
        if (url := urlsplit(value)).hostname
    }
    if not trusted and (scheme, port) != ("https", 443):
        raise ProviderError("此 API 地址或端口需要管理员放行。")
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    for _, _, _, _, address in addresses:
        ip = ipaddress.ip_address(address[0])
        if isinstance(ip, ipaddress.IPv6Address):
            if ip.ipv4_mapped:
                ip = ip.ipv4_mapped
            elif not ip.is_global or ip.sixtofour or ip.teredo or ip.scope_id:
                raise ProviderError("此 API 地址含有受限网络目标。")
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
            raise ProviderError("此 API 地址含有受限网络目标。")
        if not ip.is_global and not trusted:
            raise ProviderError("此内网 API 地址需要管理员放行。")
    if not addresses:
        raise ProviderError("无法解析 API 地址。")
    return addresses[0]


class ProviderTransport(httpx.BaseTransport):
    def __init__(self, base_url, timeout, limit, *, authenticated=True):
        origin = httpx.URL(base_url)
        self.origin = (origin.scheme, origin.raw_host.decode(), origin.port or (443 if origin.scheme == "https" else 80))
        self.timeout = timeout
        self.deadline = monotonic() + timeout
        self.limit = limit
        self.authenticated = authenticated
        self._guard = Lock()
        self._sent = False
        self.failure = None

    def handle_request(self, request):
        with self._guard:
            if self._sent:
                raise ProviderError("同一次模型调用不允许再次发送请求。")
            self._sent = True
        try:
            return self._send(request)
        except ProviderError as exc:
            self.failure = exc
            raise

    @sensitive_variables()
    def _send(self, request):
        scheme, host, port = self.origin
        url = request.url
        if (url.scheme, url.raw_host.decode(), url.port or (443 if url.scheme == "https" else 80)) != self.origin:
            raise ProviderError("提供商请求目标与已配置的 API 地址不一致。")
        # Geminis and gateways can rewrite paths. The final origin is checked before DNS and socket creation.
        try:
            family, kind, protocol, _, address = resolve_target(scheme, host, port)
        except socket.gaierror:
            raise ProviderError("无法解析 API 地址。") from None
        connection_type = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
        connection = connection_type(host, port, timeout=self.timeout)

        def connect_to_address(*args):
            sock = socket.socket(family, kind, protocol)
            try:
                remaining = self.deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError
                sock.settimeout(remaining)
                sock.connect(address)
            except OSError:
                sock.close()
                raise
            return sock

        connection._create_connection = connect_to_address
        headers = dict(request.headers)
        headers["accept-encoding"] = "identity"
        if not self.authenticated:
            headers.pop("authorization", None)
        body = request.read()
        if len(body) > 20 * 1024 * 1024:
            raise ProviderError("发送给提供商的内容超过允许的大小。")
        try:
            connection.request(request.method, url.raw_path.decode("ascii"), body=body, headers=headers)
            with connection.getresponse() as response:
                if 300 <= response.status < 400:
                    raise ProviderError("提供商返回重定向，请检查 API 地址。")
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise ProviderError("提供商返回了不支持的响应编码。")
                data = bytearray()
                while len(data) <= self.limit:
                    remaining = self.deadline - monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    if connection.sock:
                        connection.sock.settimeout(remaining)
                    chunk = response.read1(min(65536, self.limit + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                if len(data) > self.limit:
                    raise ProviderError("提供商响应超过允许的大小。")
                return httpx.Response(response.status, headers=response.getheaders(), content=bytes(data))
        except TimeoutError:
            raise httpx.ReadTimeout("API timeout", request=request) from None
        except (OSError, http.client.HTTPException):
            raise httpx.ConnectError("API connection failed", request=request) from None
        finally:
            connection.close()
