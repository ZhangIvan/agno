import os
from unittest.mock import patch

import pytest

from agno.exceptions import ModelAuthenticationError
from agno.models.volcengine import VolcengineResponses


def test_volcengine_responses_initialization_with_api_key():
    model = VolcengineResponses(id="doubao-pro-32k", api_key="test-api-key")
    assert model.id == "doubao-pro-32k"
    assert model.api_key == "test-api-key"
    assert model.base_url == "https://ark.cn-beijing.volces.com/api/v3"
    assert model.store is False


def test_volcengine_responses_initialization_without_api_key():
    with patch.dict(os.environ, {}, clear=True):
        model = VolcengineResponses(id="doubao-pro-32k")
        with pytest.raises(ModelAuthenticationError):
            model._get_client_params()


def test_volcengine_responses_initialization_with_env_key():
    with patch.dict(os.environ, {"ARK_API_KEY": "env-key"}):
        model = VolcengineResponses(id="doubao-pro-32k")
        assert model.api_key == "env-key"


def test_volcengine_responses_initialization_with_doubao_env_key():
    with patch.dict(os.environ, {"DOUBAO_API_KEY": "doubao-key"}, clear=True):
        model = VolcengineResponses(id="doubao-pro-32k")
        params = model._get_client_params()
        assert params["api_key"] == "doubao-key"


def test_volcengine_responses_client_params():
    model = VolcengineResponses(id="doubao-pro-32k", api_key="key", timeout=60.0)
    params = model._get_client_params()
    assert params["api_key"] == "key"
    assert params["base_url"] == "https://ark.cn-beijing.volces.com/api/v3"
    assert params["timeout"] == 60.0


def test_volcengine_responses_default_values():
    model = VolcengineResponses()
    assert model.id == "doubao-pro-32k"
    assert model.name == "VolcengineResponses"
    assert model.provider == "Volcengine"
    assert model.store is False


def test_volcengine_responses_no_reasoning_model():
    model = VolcengineResponses(api_key="key")
    assert model._using_reasoning_model() is False


# ============================================================
# Built-in tools
# ============================================================


def test_web_search_tool():
    model = VolcengineResponses(api_key="key", web_search=True)
    params = model.get_request_params()
    tools = params.get("tools", [])
    assert any(t.get("type") == "web_search" for t in tools)
    assert params["extra_headers"]["ark-beta-web-search"] == "true"


def test_image_process_tool():
    model = VolcengineResponses(api_key="key", image_process=True)
    params = model.get_request_params()
    tools = params.get("tools", [])
    assert any(t.get("type") == "image_process" for t in tools)
    assert params["extra_headers"]["ark-beta-image-process"] == "true"


def test_knowledge_search_tool():
    model = VolcengineResponses(
        api_key="key",
        knowledge_search={"knowledge_resource_id": "res-123", "limit": 2},
    )
    params = model.get_request_params()
    tools = params.get("tools", [])
    ks = next(t for t in tools if t.get("type") == "knowledge_search")
    assert ks["knowledge_resource_id"] == "res-123"
    assert ks["limit"] == 2
    assert params["extra_headers"]["ark-beta-knowledge-search"] == "true"


def test_mcp_servers_tool():
    model = VolcengineResponses(
        api_key="key",
        mcp_servers=[
            {"server_label": "my-server", "server_url": "https://mcp.example.com", "require_approval": "never"},
        ],
    )
    params = model.get_request_params()
    tools = params.get("tools", [])
    mcp = next(t for t in tools if t.get("type") == "mcp")
    assert mcp["server_label"] == "my-server"
    assert mcp["server_url"] == "https://mcp.example.com"
    assert params["extra_headers"]["ark-beta-mcp"] == "true"


def test_multiple_builtin_tools():
    model = VolcengineResponses(api_key="key", web_search=True, image_process=True)
    params = model.get_request_params()
    tools = params.get("tools", [])
    types = [t.get("type") for t in tools]
    assert "web_search" in types
    assert "image_process" in types
    assert params["extra_headers"]["ark-beta-web-search"] == "true"
    assert params["extra_headers"]["ark-beta-image-process"] == "true"


def test_builtin_tools_merged_with_existing_tools():
    model = VolcengineResponses(api_key="key", web_search=True)
    existing = [{"type": "function", "function": {"name": "get_weather", "arguments": "{}"}}]
    params = model.get_request_params(tools=existing)
    tools = params.get("tools", [])
    types = [t.get("type") for t in tools]
    assert "web_search" in types
    assert "function" in types


def test_no_builtin_tools_by_default():
    model = VolcengineResponses(api_key="key")
    assert model.web_search is False
    assert model.image_process is False
    assert model.knowledge_search is None
    assert model.mcp_servers is None


# ============================================================
# E2E Encryption
# ============================================================


def test_responses_encryption_header():
    model = VolcengineResponses(api_key="key", enable_encryption=True)
    params = model.get_request_params()
    assert params["extra_headers"]["x-is-encrypted"] == "true"


def test_responses_encryption_disabled_by_default():
    model = VolcengineResponses(api_key="key")
    params = model.get_request_params()
    headers = params.get("extra_headers", {})
    assert "x-is-encrypted" not in headers
