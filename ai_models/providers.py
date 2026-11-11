import json
from dataclasses import dataclass
from http.client import HTTPException
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from django.core.exceptions import ValidationError
from django.views.decorators.debug import sensitive_variables


class ProviderError(Exception):
    """可以安全显示给用户的上游错误。"""


class Provider(Protocol):
    label: str
    default_url: str
    default_model: str

    def test_payload(self, model_id: str, thinking: str, reasoning_effort: str) -> dict: ...

    def test(self, base_url: str, payload: dict, api_key: str) -> str: ...


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class DeepSeekProvider:
    label: str = "DeepSeek"
    default_url: str = "https://api.deepseek.com"
    default_model: str = "deepseek-flash"

    def test_payload(self, model_id: str, thinking: str, reasoning_effort: str) -> dict:
        enabled = thinking == "enabled"
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "请回复：连接成功。"}],
            "max_tokens": 2048 if enabled else 16,
            "thinking": {"type": thinking},
            "stream": False,
        }
        if enabled:
            payload["reasoning_effort"] = reasoning_effort
        return payload

    @sensitive_variables()
    def test(self, base_url: str, payload: dict, api_key: str) -> str:
        request = Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        opener = build_opener(ProxyHandler({}), RejectRedirects())
        try:
            with opener.open(request, timeout=25 if payload["thinking"]["type"] == "enabled" else 10) as response:
                body = response.read(65537)
        except HTTPError as exc:
            code = exc.code
            exc.close()
            message = {
                400: "请求参数有误，请检查模型 ID 和 API 地址。",
                401: "认证失败，请检查 API 密钥。",
                402: "API 账号余额不足。",
                403: "提供商拒绝访问，请检查密钥权限。",
                404: "未找到模型或接口，请检查模型 ID 和 API 地址。",
                422: "请求参数有误，请检查模型 ID 和 API 地址。",
                429: "提供商限制了请求频率，请稍后重试。",
            }.get(code, "提供商暂时无法处理请求。" if code >= 500 else "提供商返回了意外状态。")
            raise ProviderError(message) from None
        except TimeoutError:
            raise ProviderError("请求超时，请稍后重试。") from None
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise ProviderError("请求超时，请稍后重试。") from None
            raise ProviderError("无法连接提供商，请检查 API 地址或网络。") from None
        except (HTTPException, OSError):
            raise ProviderError("连接中断，请稍后重试。") from None

        if len(body) > 65536:
            raise ProviderError("提供商响应超过测试允许的大小。")
        try:
            content = json.loads(body)["choices"][0]["message"]["content"]
            if isinstance(content, str) and content.strip():
                return content
        except (ValueError, KeyError, IndexError, TypeError):
            pass
        raise ProviderError("提供商未返回有效的文本生成结果。")


PROVIDERS: dict[str, Provider] = {"deepseek": DeepSeekProvider()}


def validate_base_url(provider: str, value: str) -> str:
    adapter = PROVIDERS.get(provider)
    if adapter is None:
        raise ValidationError("请选择已支持的模型提供商。")
    value = value.rstrip("/") if value else adapter.default_url
    try:
        parts = urlsplit(value)
        valid = (
            parts.scheme in {"http", "https"}
            and parts.hostname
            and parts.username is None
            and parts.password is None
            and "@" not in parts.netloc
            and not any(char.isspace() or ord(char) < 32 for char in value)
            and not any(char in value for char in "?#\\")
            and (parts.port is None or 1 <= parts.port <= 65535)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValidationError("请输入完整的 HTTP 或 HTTPS API 基址，地址应省略用户名、密码、查询参数和片段。")
    return value
