from django.core.exceptions import ValidationError
from django.views.decorators.debug import sensitive_variables

import httpx

from ai.providers import PROVIDERS, ProviderError, validate_model_id

from .client import CONCURRENT_REQUESTS, STATUS_MESSAGES
from .transport import ProviderTransport

MAX_MODELS = 200


@sensitive_variables()
def fetch_model_ids(provider, base_url, api_key):
    is_ollama = provider == "ollama"
    if not is_ollama and not PROVIDERS[provider].model_list_path:
        raise ProviderError("此提供商暂不支持获取模型列表。")
    if is_ollama:
        url = f"{base_url.removesuffix('/api')}/api/tags"
    else:
        url = f"{base_url}{PROVIDERS[provider].model_list_path}"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    transport = ProviderTransport(base_url, timeout=8, limit=512 * 1024, authenticated=bool(api_key))
    if not CONCURRENT_REQUESTS.acquire(blocking=False):
        raise ProviderError("当前模型请求较多，请稍后重试。")
    try:
        with httpx.Client(transport=transport, trust_env=False, follow_redirects=False) as client:
            response = client.get(url, headers=headers)
        if response.status_code in {404, 405, 501}:
            raise ProviderError("此 API 地址未提供模型列表，请手动输入模型 ID。")
        if not response.is_success:
            raise ProviderError(STATUS_MESSAGES.get(response.status_code, "获取模型列表失败。"))
        payload = response.json()
        models = payload.get("models" if is_ollama else "data") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            raise ValueError
    except httpx.TimeoutException:
        raise ProviderError("获取模型列表超时，请稍后重试。") from None
    except httpx.RequestError:
        raise ProviderError("无法连接提供商，请检查 API 地址或网络。") from None
    except (ValueError, RecursionError):
        raise ProviderError("提供商返回的模型列表格式无效。") from None
    finally:
        CONCURRENT_REQUESTS.release()

    ids = set()
    for item in models:
        if not isinstance(item, dict):
            continue
        model_id = (item.get("name") or item.get("model")) if is_ollama else item.get("id")
        if not isinstance(model_id, str) or len(model_id) > 150 or (api_key and api_key in model_id):
            continue
        try:
            ids.add(validate_model_id(model_id))
        except ValidationError:
            continue
    return sorted(ids, key=lambda value: (value.casefold(), value))[:MAX_MODELS]
