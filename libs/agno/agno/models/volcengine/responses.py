import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel

from agno.exceptions import ModelAuthenticationError
from agno.models.message import Message
from agno.models.openai.open_responses import OpenResponses
from agno.models.volcengine._tools import inject_builtin_tools


@dataclass
class VolcengineResponses(OpenResponses):
    """Volcengine Ark Responses API model.

    Uses the OpenAI-compatible ``/v1/responses`` endpoint on the Volcengine Ark
    platform.  The Responses API provides a different interaction model from Chat
    Completions — it uses structured input/output blocks, supports server-side
    state via ``previous_response_id``, and offers background polling.

    Authentication (pick one):
      * API key  — ``ARK_API_KEY`` (or ``DOUBAO_API_KEY``) or ``api_key=``.
      * AK / SK  — ``VOLC_ACCESSKEY`` / ``VOLC_SECRETKEY`` (via ``ak=`` / ``sk=``).

    Note: AK/SK auth is handled at the Volcengine SDK level and is **not**
    directly compatible with the standard ``openai`` client used by
    ``OpenResponses``.  If you need AK/SK auth, use the ``Ark`` (Chat
    Completions) model instead.  This class requires an API key.

    Built-in tools (Responses API only):
      * ``web_search`` — enable web search via ``web_search=True``.
      * ``image_process`` — enable image processing via ``image_process=True``.
      * ``knowledge_search`` — pass config dict with ``knowledge_resource_id``.
      * ``mcp_servers`` — list of MCP server config dicts.

    Example::

        from agno.models.volcengine import VolcengineResponses
        model = VolcengineResponses(id="doubao-pro-32k", api_key="key", web_search=True)
    """

    id: str = "doubao-pro-32k"
    name: str = "VolcengineResponses"
    provider: str = "Volcengine"

    api_key: Optional[str] = field(default_factory=lambda: os.getenv("ARK_API_KEY"))
    base_url: str = "https://ark.cn-beijing.volces.com/api/v3"

    # E2E encryption (Responses API uses openai client; encryption header is
    # passed through but client-side encrypt/decrypt is handled server-side)
    enable_encryption: bool = False

    # Volcengine Responses API is stateless (no previous_response_id support)
    store: Optional[bool] = False

    # Volcengine built-in tools (Responses API only)
    web_search: bool = False
    image_process: bool = False
    knowledge_search: Optional[Dict[str, Any]] = None
    mcp_servers: Optional[List[Dict[str, Any]]] = None

    def _get_client_params(self) -> Dict[str, Any]:
        if not self.api_key:
            self.api_key = os.getenv("ARK_API_KEY") or os.getenv("DOUBAO_API_KEY")
        if not self.api_key:
            raise ModelAuthenticationError(
                message="ARK_API_KEY (or DOUBAO_API_KEY) not set. The Volcengine Responses API requires an API key.",
                model_name=self.name,
            )

        params: Dict[str, Any] = {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "default_headers": self.default_headers,
            "default_query": self.default_query,
        }
        params = {k: v for k, v in params.items() if v is not None}
        if self.client_params:
            params.update(self.client_params)
        return params

    def get_request_params(
        self,
        messages: Optional[List[Message]] = None,
        response_format: Optional[Union[Dict, Type[BaseModel]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        params = super().get_request_params(
            messages=messages,
            response_format=response_format,
            tools=tools,
            tool_choice=tool_choice,
        )

        if self.enable_encryption:
            headers = params.get("extra_headers") or {}
            headers["x-is-encrypted"] = "true"
            params["extra_headers"] = headers

        params = inject_builtin_tools(
            params,
            web_search=self.web_search,
            image_process=self.image_process,
            knowledge_search=self.knowledge_search,
            mcp_servers=self.mcp_servers,
        )

        return params
