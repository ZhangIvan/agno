import os
from unittest.mock import patch

import pytest

from agno.exceptions import ModelAuthenticationError
from agno.models.volcengine import Ark


# ============================================================
# Initialization & auth
# ============================================================


def test_ark_initialization_with_api_key():
    model = Ark(id="doubao-pro-32k", api_key="test-api-key")
    assert model.id == "doubao-pro-32k"
    assert model.api_key == "test-api-key"
    assert model.base_url == "https://ark.cn-beijing.volces.com/api/v3"


def test_ark_initialization_without_credentials():
    with patch.dict(os.environ, {}, clear=True):
        model = Ark(id="doubao-pro-32k")
        with pytest.raises(ModelAuthenticationError):
            model._get_client_params()


def test_ark_initialization_with_env_api_key():
    with patch.dict(os.environ, {"ARK_API_KEY": "env-api-key"}):
        model = Ark(id="doubao-pro-32k")
        assert model.api_key == "env-api-key"


def test_ark_initialization_with_doubao_env_key():
    with patch.dict(os.environ, {"DOUBAO_API_KEY": "doubao-key"}, clear=True):
        model = Ark(id="doubao-pro-32k")
        assert model.api_key is None
        params = model._get_client_params()
        assert params["api_key"] == "doubao-key"


def test_ark_client_params_api_key():
    model = Ark(id="doubao-pro-32k", api_key="test-api-key")
    params = model._get_client_params()
    assert params["api_key"] == "test-api-key"
    assert params["base_url"] == "https://ark.cn-beijing.volces.com/api/v3"
    assert "ak" not in params
    assert "sk" not in params


def test_ark_client_params_ak_sk():
    model = Ark(id="doubao-pro-32k", ak="access-key", sk="secret-key")
    params = model._get_client_params()
    assert "api_key" not in params
    assert params["ak"] == "access-key"
    assert params["sk"] == "secret-key"


def test_ark_client_params_with_region():
    model = Ark(id="doubao-pro-32k", api_key="key", region="cn-beijing")
    params = model._get_client_params()
    assert params["region"] == "cn-beijing"


def test_ark_client_params_with_custom_timeout():
    model = Ark(id="doubao-pro-32k", api_key="key", timeout=60.0)
    params = model._get_client_params()
    assert params["timeout"] == 60.0


def test_ark_default_values():
    model = Ark()
    assert model.id == "doubao-pro-32k"
    assert model.name == "Volcengine"
    assert model.provider == "Volcengine"
    assert model.thinking is None
    assert model.reasoning_effort is None
    assert model.repetition_penalty is None
    assert model.caching is None
    assert model.region is None
    assert model.web_search is False
    assert model.image_process is False
    assert model.knowledge_search is None
    assert model.mcp_servers is None


# ============================================================
# Request params
# ============================================================


def test_ark_request_params_volcengine_specific():
    model = Ark(
        id="doubao-pro-32k",
        api_key="key",
        thinking={"type": "enabled", "budget_tokens": 1024},
        reasoning_effort="high",
        repetition_penalty=1.2,
    )
    params = model.get_request_params()
    assert params["thinking"] == {"type": "enabled", "budget_tokens": 1024}
    assert params["reasoning_effort"] == "high"
    assert params["repetition_penalty"] == 1.2


def test_ark_request_params_no_volcengine_extras():
    model = Ark(id="doubao-pro-32k", api_key="key")
    params = model.get_request_params()
    assert "thinking" not in params
    assert "reasoning_effort" not in params
    assert "repetition_penalty" not in params


# ============================================================
# Response parsing
# ============================================================


def _build_chat_completion(
    content="Hello!",
    reasoning_content=None,
    tool_calls=None,
    finish_reason="stop",
    moderation_hit_type=None,
    prompt_tokens=10,
    completion_tokens=20,
    total_tokens=30,
    reasoning_tokens=None,
    cached_tokens=None,
):
    """Build a mock ChatCompletion response from Ark SDK types."""
    from volcenginesdkarkruntime.types.chat import ChatCompletion
    from volcenginesdkarkruntime.types.chat.chat_completion_message import ChatCompletionMessage

    message = ChatCompletionMessage(
        content=content,
        role="assistant",
        reasoning_content=reasoning_content,
        tool_calls=tool_calls,
    )

    choice = {
        "message": message,
        "finish_reason": finish_reason,
        "index": 0,
    }
    if moderation_hit_type:
        from volcenginesdkarkruntime.types.chat.chat_completion import Choice

        choice_obj = Choice.model_construct(**choice)
        choice_obj.__dict__["moderation_hit_type"] = moderation_hit_type
    else:
        from volcenginesdkarkruntime.types.chat.chat_completion import Choice

        choice_obj = Choice.model_construct(**choice)

    usage = None
    if prompt_tokens is not None:
        from volcenginesdkarkruntime.types.completion_usage import CompletionUsage

        usage_kwargs = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        if cached_tokens is not None or reasoning_tokens is not None:
            from volcenginesdkarkruntime.types.completion_usage import (
                CompletionTokensDetails,
                PromptTokensDetails,
            )

            prompt_details = None
            if cached_tokens is not None:
                prompt_details = PromptTokensDetails(cached_tokens=cached_tokens)
            completion_details = None
            if reasoning_tokens is not None:
                completion_details = CompletionTokensDetails(reasoning_tokens=reasoning_tokens)
            usage_kwargs["prompt_tokens_details"] = prompt_details
            usage_kwargs["completion_tokens_details"] = completion_details

        usage = CompletionUsage(**usage_kwargs)

    return ChatCompletion.model_construct(
        id="chatcmpl-test",
        choices=[choice_obj],
        created=1234567890,
        model="doubao-pro-32k",
        object="chat.completion",
        usage=usage,
    )


def test_parse_response_basic_content():
    model = Ark(id="doubao-pro-32k", api_key="key")
    resp = _build_chat_completion(content="Hello from Doubao!")
    parsed = model._parse_provider_response(resp)
    assert parsed.content == "Hello from Doubao!"
    assert parsed.role == "assistant"
    assert parsed.provider_data["id"] == "chatcmpl-test"


def test_parse_response_reasoning_content():
    model = Ark(id="doubao-pro-32k", api_key="key")
    resp = _build_chat_completion(
        content="Final answer",
        reasoning_content="Let me think step by step...",
    )
    parsed = model._parse_provider_response(resp)
    assert parsed.content == "Final answer"
    assert parsed.reasoning_content == "Let me think step by step..."


def test_parse_response_metrics():
    model = Ark(id="doubao-pro-32k", api_key="key")
    resp = _build_chat_completion(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cached_tokens=80,
        reasoning_tokens=20,
    )
    parsed = model._parse_provider_response(resp)
    metrics = parsed.response_usage
    assert metrics is not None
    assert metrics.input_tokens == 100
    assert metrics.output_tokens == 50
    assert metrics.total_tokens == 150
    assert metrics.cache_read_tokens == 80
    assert metrics.reasoning_tokens == 20


def test_parse_response_metrics_no_details():
    model = Ark(id="doubao-pro-32k", api_key="key")
    resp = _build_chat_completion(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )
    parsed = model._parse_provider_response(resp)
    metrics = parsed.response_usage
    assert metrics is not None
    assert metrics.input_tokens == 10
    assert metrics.output_tokens == 5
    assert metrics.cache_read_tokens == 0
    assert metrics.reasoning_tokens == 0


def test_parse_response_moderation_hit():
    model = Ark(id="doubao-pro-32k", api_key="key")
    resp = _build_chat_completion(moderation_hit_type="violence")
    parsed = model._parse_provider_response(resp)
    assert parsed.provider_data.get("moderation_hit_type") == "violence"


def test_parse_response_no_system_fingerprint():
    """Ark ChatCompletion does not have system_fingerprint — must not crash."""
    model = Ark(id="doubao-pro-32k", api_key="key")
    resp = _build_chat_completion()
    parsed = model._parse_provider_response(resp)
    assert "system_fingerprint" not in (parsed.provider_data or {})


# ============================================================
# Streaming delta parsing
# ============================================================


def _build_chunk(content=None, reasoning_content=None, finish_reason=None, usage=None):
    """Build a mock ChatCompletionChunk."""
    from volcenginesdkarkruntime.types.chat import ChatCompletionChunk
    from volcenginesdkarkruntime.types.chat.chat_completion_chunk import ChoiceDelta

    delta_kwargs = {}
    if content is not None:
        delta_kwargs["content"] = content
    if reasoning_content is not None:
        delta_kwargs["reasoning_content"] = reasoning_content
    delta = ChoiceDelta.model_construct(**delta_kwargs)

    choice_kwargs = {"delta": delta, "index": 0}
    if finish_reason is not None:
        choice_kwargs["finish_reason"] = finish_reason

    from volcenginesdkarkruntime.types.chat.chat_completion_chunk import Choice

    choice = Choice.model_construct(**choice_kwargs)

    return ChatCompletionChunk.model_construct(
        id="chatcmpl-test",
        choices=[choice],
        created=1234567890,
        model="doubao-pro-32k",
        object="chat.completion.chunk",
        usage=usage,
    )


def test_parse_delta_content():
    model = Ark(id="doubao-pro-32k", api_key="key")
    chunk = _build_chunk(content="Hello ")
    parsed = model._parse_provider_response_delta(chunk)
    assert parsed.content == "Hello "


def test_parse_delta_reasoning_content():
    model = Ark(id="doubao-pro-32k", api_key="key")
    chunk = _build_chunk(reasoning_content="Thinking...")
    parsed = model._parse_provider_response_delta(chunk)
    assert parsed.reasoning_content == "Thinking..."


# ============================================================
# Built-in tools
# ============================================================


def test_ark_web_search_tool():
    model = Ark(api_key="key", web_search=True)
    params = model.get_request_params()
    tools = params.get("tools", [])
    assert any(t.get("type") == "web_search" for t in tools)
    assert params["extra_headers"]["ark-beta-web-search"] == "true"


def test_ark_image_process_tool():
    model = Ark(api_key="key", image_process=True)
    params = model.get_request_params()
    tools = params.get("tools", [])
    assert any(t.get("type") == "image_process" for t in tools)
    assert params["extra_headers"]["ark-beta-image-process"] == "true"


def test_ark_knowledge_search_tool():
    model = Ark(
        api_key="key",
        knowledge_search={"knowledge_resource_id": "res-456", "limit": 3},
    )
    params = model.get_request_params()
    tools = params.get("tools", [])
    ks = next(t for t in tools if t.get("type") == "knowledge_search")
    assert ks["knowledge_resource_id"] == "res-456"
    assert ks["limit"] == 3
    assert params["extra_headers"]["ark-beta-knowledge-search"] == "true"


def test_ark_mcp_servers_tool():
    model = Ark(
        api_key="key",
        mcp_servers=[
            {"server_label": "test", "server_url": "https://mcp.test.com", "require_approval": "never"},
        ],
    )
    params = model.get_request_params()
    tools = params.get("tools", [])
    mcp = next(t for t in tools if t.get("type") == "mcp")
    assert mcp["server_label"] == "test"
    assert params["extra_headers"]["ark-beta-mcp"] == "true"


def test_ark_builtin_tools_with_function_tools():
    model = Ark(api_key="key", web_search=True)
    existing = [{"type": "function", "function": {"name": "get_weather", "arguments": "{}"}}]
    params = model.get_request_params(tools=existing)
    tools = params.get("tools", [])
    types = [t.get("type") for t in tools]
    assert "web_search" in types
    assert "function" in types


def test_ark_builtin_tools_with_thinking():
    model = Ark(
        api_key="key",
        web_search=True,
        thinking={"type": "enabled", "budget_tokens": 1024},
    )
    params = model.get_request_params()
    assert params["thinking"] == {"type": "enabled", "budget_tokens": 1024}
    tools = params.get("tools", [])
    assert any(t.get("type") == "web_search" for t in tools)


# ============================================================
# E2E Encryption
# ============================================================


def test_ark_encryption_header():
    model = Ark(api_key="key", enable_encryption=True)
    params = model.get_request_params()
    assert params["extra_headers"]["x-is-encrypted"] == "true"


def test_ark_encryption_disabled_by_default():
    model = Ark(api_key="key")
    params = model.get_request_params()
    headers = params.get("extra_headers", {})
    assert "x-is-encrypted" not in headers


def test_ark_encryption_with_web_search():
    model = Ark(api_key="key", enable_encryption=True, web_search=True)
    params = model.get_request_params()
    assert params["extra_headers"]["x-is-encrypted"] == "true"
    assert params["extra_headers"]["ark-beta-web-search"] == "true"


# ============================================================
# Caching
# ============================================================


def test_ark_caching_in_extra_body():
    model = Ark(api_key="key", caching={"type": "enabled"})
    params = model.get_request_params()
    assert params["extra_body"]["caching"] == {"type": "enabled"}


def test_ark_caching_default_none():
    model = Ark(api_key="key")
    params = model.get_request_params()
    assert "extra_body" not in params or params.get("extra_body") is None


def test_ark_caching_with_existing_extra_body():
    model = Ark(api_key="key", caching={"type": "enabled"}, extra_body={"custom_key": "value"})
    params = model.get_request_params()
    assert params["extra_body"]["caching"] == {"type": "enabled"}
    assert params["extra_body"]["custom_key"] == "value"


def test_ark_caching_does_not_overwrite_extra_body_caching():
    model = Ark(
        api_key="key",
        caching={"type": "enabled"},
        extra_body={"caching": {"type": "disabled"}},
    )
    params = model.get_request_params()
    assert params["extra_body"]["caching"] == {"type": "disabled"}


def test_ark_caching_with_thinking():
    model = Ark(
        api_key="key",
        caching={"type": "enabled"},
        thinking={"type": "enabled", "budget_tokens": 1024},
    )
    params = model.get_request_params()
    assert params["thinking"] == {"type": "enabled", "budget_tokens": 1024}
    assert params["extra_body"]["caching"] == {"type": "enabled"}
