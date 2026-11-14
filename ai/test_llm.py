import json
import socket
from types import SimpleNamespace

import httpx
import pytest

from .llm.client import GenerationRequest, invoke
from .llm.transport import resolve_target
from .providers import ProviderError

KEY = "synthetic-api-key"


@pytest.mark.parametrize(("provider", "model_id", "base_url", "path"), [
    ("openai", "gpt-test", "https://api.openai.com/v1", "/v1/chat/completions"),
    ("dashscope", "qwen-test", "https://dashscope.aliyuncs.com/compatible-mode/v1", "/compatible-mode/v1/chat/completions"),
    ("openrouter", "vendor/test", "https://openrouter.ai/api/v1", "/api/v1/chat/completions"),
    ("gemini", "gemini-test", "https://generativelanguage.googleapis.com/v1beta", "/v1beta/models/gemini-test:generateContent"),
    ("ollama", "local-model", "http://localhost:11434", "/api/chat"),
    ("deepseek", "deepseek-flash", "https://api.deepseek.com", "/chat/completions"),
    ("anthropic", "claude-test", "https://api.anthropic.com", "/v1/messages"),
    ("custom", "server/model", "https://api.example.test/v1", "/v1/chat/completions"),
])
def test_sdk_routes_through_scoped_transport(monkeypatch, provider, model_id, base_url, path):
    seen = []

    def send(transport, request):
        seen.append((request.url.path, request.url.host))
        assert request.url.path == path
        assert request.url.host == httpx.URL(base_url).host
        credential = request.headers.get("Authorization", request.headers.get("x-api-key", ""))
        if provider != "gemini":
            assert KEY in credential
        body = json.loads(request.content)
        if provider != "gemini":
            assert body["model"] == model_id
        if provider == "deepseek":
            assert body["thinking"] == {"type": "enabled"}
            assert body["reasoning_effort"] == "high"
            assert body["response_format"] == {"type": "json_object"}
            assert body["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png")
        if provider == "anthropic":
            data = {
                "id": "test", "type": "message", "role": "assistant", "model": model_id,
                "content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        elif provider == "gemini":
            data = {
                "candidates": [{"content": {"role": "model", "parts": [{"text": "{}"}]}, "finishReason": "STOP"}],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1, "totalTokenCount": 2},
            }
        elif provider == "ollama":
            data = {"model": model_id, "message": {"role": "assistant", "content": "{}"}, "done": True, "done_reason": "stop"}
        else:
            data = {
                "id": "test", "model": model_id, "object": "chat.completion", "created": 0,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "{}"}, "finish_reason": "stop"}],
            }
        return httpx.Response(200, json=data)

    monkeypatch.setattr("ai.llm.transport.ProviderTransport.handle_request", send)
    model = SimpleNamespace(provider=provider, model_id=model_id, base_url=base_url)
    if provider != "deepseek":
        monkeypatch.setattr("ai.llm.client.capability", lambda *args: False)
    messages = [{"role": "user", "content": "测试"}]
    if provider == "deepseek":
        messages[0]["content"] = [
            {"type": "text", "text": "测试"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,aW1hZ2U="}},
        ]
    try:
        result = invoke(model, GenerationRequest(
        messages, 256, response_mode="json", thinking="enabled" if provider == "deepseek" else "",
        reasoning_effort="high", images=provider == "deepseek",
        ), KEY)
    except ProviderError:
        pytest.fail(f"SDK 请求路径：{seen}")
    assert result == "{}"


@pytest.mark.parametrize(("status", "message"), [(401, "认证失败"), (402, "余额不足"), (429, "请求频率")])
def test_sdk_does_not_expose_error_body(monkeypatch, status, message):
    def send(transport, request):
        return httpx.Response(status, json={"error": {"message": KEY}})

    monkeypatch.setattr("ai.llm.transport.ProviderTransport.handle_request", send)
    model = SimpleNamespace(provider="custom", model_id="test", base_url="https://api.example.test/v1")
    with pytest.raises(ProviderError, match=message) as error:
        invoke(model, GenerationRequest([{"role": "user", "content": "测试"}], 64), KEY)
    assert KEY not in str(error.value)


def test_mixed_dns_results_blocked(monkeypatch, settings):
    settings.AI_TRUSTED_ENDPOINTS = []
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 443)),
    ])
    with pytest.raises(ProviderError, match="管理员放行"):
        resolve_target("https", "api.example.test", 443)


def test_transport_rejects_cross_origin_before_dns(monkeypatch):
    from .llm.transport import ProviderTransport

    def unexpected_dns(*args):
        pytest.fail("跨源请求不应进行 DNS 查询")

    monkeypatch.setattr("ai.llm.transport.resolve_target", unexpected_dns)
    transport = ProviderTransport("https://api.example.test", 10, 1024)
    with pytest.raises(ProviderError, match="请求目标"):
        transport.handle_request(httpx.Request("POST", "https://other.example.test/v1"))


@pytest.mark.parametrize(("finish", "reply", "message"), [
    ("length", "{}", "未返回完整正文"),
    ("stop", "invalid", "有效的 JSON"),
    ("stop", "[]", "有效的 JSON"),
])
def test_generation_rejects_incomplete_or_invalid_json(monkeypatch, finish, reply, message):
    def send(transport, request):
        return httpx.Response(200, json={
            "id": "test", "model": "test", "object": "chat.completion", "created": 0,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": finish}],
        })

    monkeypatch.setattr("ai.llm.transport.ProviderTransport.handle_request", send)
    monkeypatch.setattr("ai.llm.client.capability", lambda *args: False)
    model = SimpleNamespace(provider="custom", model_id="test", base_url="https://api.example.test/v1")
    with pytest.raises(ProviderError, match=message):
        invoke(model, GenerationRequest([{"role": "user", "content": "测试"}], 64, response_mode="json"), KEY)


@pytest.mark.parametrize(("provider", "base", "path", "payload", "key"), [
    ("custom", "https://example.test/v1", "/v1/models", {"data": [{"id": "a/b"}, {"id": "a/b"}]}, KEY),
    ("ollama", "http://localhost:11434", "/api/tags", {"models": [{"name": "a/b"}]}, ""),
])
def test_discovery_uses_bounded_transport(monkeypatch, provider, base, path, payload, key):
    from .llm.discovery import fetch_model_ids

    def send(transport, request):
        assert request.method == "GET"
        assert request.url.path == path
        assert request.headers.get("authorization") == (f"Bearer {key}" if key else None)
        assert transport.limit == 512 * 1024
        return httpx.Response(200, json=payload)

    monkeypatch.setattr("ai.llm.transport.ProviderTransport.handle_request", send)
    assert fetch_model_ids(provider, base, key) == ["a/b"]
