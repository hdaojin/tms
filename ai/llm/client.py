import json
from dataclasses import dataclass
from threading import BoundedSemaphore

import httpx
from django.views.decorators.debug import sensitive_variables

from ai.providers import PROVIDERS, ProviderError, capability, supports_images, validate_base_url, validate_model_id

from .transport import ProviderTransport

CONCURRENT_REQUESTS = BoundedSemaphore(4)
STATUS_MESSAGES = {
    400: "请求参数与模型或 API 协议不兼容。",
    401: "认证失败，请检查 API 密钥。",
    402: "API 账号余额不足。",
    403: "提供商拒绝访问，请检查密钥权限。",
    404: "未找到模型或接口，请检查模型 ID 和 API 地址。",
    422: "请求参数与模型或 API 协议不兼容。",
    429: "提供商限制了请求频率，请稍后重试。",
}


@dataclass(frozen=True)
class GenerationRequest:
    messages: list
    max_output_tokens: int
    response_mode: str = "text"
    thinking: str = ""
    reasoning_effort: str = ""
    timeout: int = 120
    response_limit: int = 2 * 1024 * 1024
    images: bool = False


@sensitive_variables()
def invoke(model, request, key):
    import litellm
    import openai
    from litellm.llms.custom_httpx.http_handler import HTTPHandler

    provider = PROVIDERS[model.provider]
    base_url = validate_base_url(model.provider, model.base_url)
    model_id = validate_model_id(model.model_id)
    if not key and provider.key_required:
        raise ProviderError("请先配置 API 密钥。")
    image_parts = [
        part
        for message in request.messages if isinstance(message.get("content"), list)
        for part in message["content"] if part.get("type") == "image_url"
    ]
    if (request.images or image_parts) and not supports_images(model):
        raise ProviderError("此模型未确认支持图片输入，请选择仅生成正文。")
    if any(
        not part.get("image_url", {}).get("url", "").startswith(
            ("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,")
        )
        for part in image_parts
    ):
        raise ProviderError("图片必须使用受支持的内联格式。")

    parameters = {}
    if model.provider == "deepseek":
        if request.thinking:
            parameters["extra_body"] = {"thinking": {"type": request.thinking}}
        if request.thinking == "enabled" and request.reasoning_effort:
            parameters["reasoning_effort"] = request.reasoning_effort
    elif request.thinking == "enabled":
        raise ProviderError("此模型未配置思考模式。")
    request_messages = request.messages
    if request.response_mode == "json" and (
        model.provider == "deepseek" or capability(model, "supports_json")
    ):
        parameters["response_format"] = {"type": "json_object"}
    elif request.response_mode == "json":
        request_messages = [*request.messages, {"role": "user", "content": "请只返回一个有效的 JSON 对象。"}]

    transport = ProviderTransport(base_url, request.timeout, request.response_limit, authenticated=bool(key))
    if not CONCURRENT_REQUESTS.acquire(blocking=False):
        raise ProviderError("当前模型请求较多，请稍后重试。")
    try:
        with httpx.Client(transport=transport, trust_env=False, follow_redirects=False) as http:
            if provider.openai_client:
                sdk_client = openai.OpenAI(
                    api_key=key, base_url=base_url, http_client=http, max_retries=0, timeout=request.timeout
                )
            else:
                sdk_client = HTTPHandler(client=http, follow_redirects=False)
            response = litellm.completion(
                model=f"{provider.route}/{model_id}",
                custom_llm_provider=provider.route,
                api_base=base_url,
                api_key=key or "ollama-no-auth",
                client=sdk_client,
                messages=request_messages,
                max_tokens=request.max_output_tokens,
                timeout=request.timeout,
                stream=False,
                num_retries=0,
                caching=False,
                drop_params=False,
                **{"no-log": True},
                **parameters,
            )
    except ProviderError:
        raise
    except (litellm.Timeout, TimeoutError):
        raise ProviderError("请求超时，请稍后重试。") from None
    except Exception as exc:
        if transport.failure is not None:
            raise transport.failure from None
        status = getattr(exc, "status_code", None)
        raise ProviderError(STATUS_MESSAGES.get(status, "模型服务连接失败或返回了无效结果。")) from None
    finally:
        CONCURRENT_REQUESTS.release()

    try:
        choice = response.choices[0]
        content = choice.message.content
        if choice.finish_reason != "stop":
            raise ProviderError("模型未返回完整正文，请缩短素材或调整篇幅后重试。")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("提供商未返回有效的文本生成结果。")
        if key:
            content = content.replace(key, "[已隐藏]")
        if request.response_mode == "json" and not isinstance(json.loads(content), dict):
            raise ValueError
    except (AttributeError, IndexError, TypeError):
        raise ProviderError("提供商未返回有效的文本生成结果。") from None
    except (ValueError, RecursionError):
        raise ProviderError("模型未返回有效的 JSON 对象。") from None
    return content
