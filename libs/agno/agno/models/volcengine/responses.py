import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from pydantic import BaseModel

from agno.exceptions import ModelAuthenticationError
from agno.models.message import Message
from agno.models.openai.open_responses import OpenResponses
from agno.models.response import ModelResponse
from agno.models.volcengine._tools import inject_builtin_tools


@dataclass
class VolcengineResponses(OpenResponses):
    """Volcengine Ark Responses API model.

    Uses the OpenAI-compatible ``/v1/responses`` endpoint on the Volcengine Ark
    platform.  The Responses API provides a different interaction model from Chat
    Completions — it uses structured input/output blocks, supports server-side
    state via ``previous_response_id``, and offers background polling.

    Authentication:
      * API key  — ``ARK_API_KEY`` (or ``DOUBAO_API_KEY``) or ``api_key=``.

    Note: AK/SK auth requires the ``volcenginesdkarkruntime`` SDK and is **not**
    compatible with the standard ``openai`` client used by this class.  If you
    need AK/SK auth, use the ``Ark`` (Chat Completions) model instead.

    Server-side state (``store=True`` by default):
      Responses are stored server-side and subsequent requests within the same
      session automatically carry ``previous_response_id`` so the API reuses
      cached context instead of re-processing full history.  Set ``store=False``
      to disable this behavior (all history sent on every request).

    Context caching:
      * ``caching`` — pass ``{"type": "enabled"}`` to enable Volcengine context
        caching via ``extra_body``.

    Built-in tools (Responses API only):
      * ``web_search`` — enable web search via ``web_search=True``.
      * ``image_process`` — enable image processing via ``image_process=True``.
      * ``knowledge_search`` — pass config dict with ``knowledge_resource_id``.
      * ``mcp_servers`` — list of MCP server config dicts.

    Note: Inherited ``reasoning``, ``reasoning_effort``, and ``reasoning_summary``
    fields are OpenAI-specific and have no effect on Volcengine models.

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

    # Enable server-side state — allows previous_response_id chaining so the
    # API can reuse cached context instead of re-processing full history.
    store: Optional[bool] = True

    # Volcengine built-in tools (Responses API only)
    web_search: bool = False
    image_process: bool = False
    knowledge_search: Optional[Dict[str, Any]] = None
    mcp_servers: Optional[List[Dict[str, Any]]] = None

    # Volcengine-specific request parameters (pass-through)
    caching: Optional[Dict[str, Any]] = None

    def _using_reasoning_model(self) -> bool:
        """Enable previous_response_id chaining for all Volcengine models.

        The Responses API's ``previous_response_id`` mechanism works for any
        model, not just reasoning models.  Returning ``True`` here activates
        the ``store=True`` + ``previous_response_id`` logic inherited from
        ``OpenAIResponses``.
        """
        return True

    def _set_reasoning_request_param(self, base_params: Dict[str, Any]) -> Dict[str, Any]:
        """Volcengine does not use the OpenAI ``reasoning`` parameter — skip it."""
        return base_params

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

        if self.caching is not None:
            body = params.get("extra_body") or {}
            body.setdefault("caching", self.caching)
            params["extra_body"] = body

        params = inject_builtin_tools(
            params,
            web_search=self.web_search,
            image_process=self.image_process,
            knowledge_search=self.knowledge_search,
            mcp_servers=self.mcp_servers,
        )

        return params

    def _strip_redundant_provider_data(self, model_response: ModelResponse) -> None:
        """Strip redundant fields from provider_data that waste context length.

        Volcengine returns reasoning_output with encrypted_content (large base64 blob)
        and summary text that duplicates reasoning_content. These are only needed for
        server-side state restoration (store=False ZDR mode) and should not be sent
        to the client.
        """
        if model_response.provider_data is None:
            return

        reasoning_output = model_response.provider_data.get("reasoning_output")
        if not isinstance(reasoning_output, dict):
            return

        # Remove encrypted_content — large base64 blob not useful client-side
        reasoning_output.pop("encrypted_content", None)

        # Remove summary text that duplicates reasoning_content
        if model_response.reasoning_content and reasoning_output.get("summary"):
            reasoning_output.pop("summary", None)

        # If reasoning_output is now empty or only has type, remove it entirely
        if not reasoning_output or (len(reasoning_output) == 1 and "type" in reasoning_output):
            model_response.provider_data.pop("reasoning_output", None)

    def _parse_provider_response(self, response, **kwargs) -> ModelResponse:
        model_response = super()._parse_provider_response(response, **kwargs)
        self._strip_redundant_provider_data(model_response)
        return model_response

    def _parse_provider_response_delta(
        self, stream_event, assistant_message: Message, tool_use: Dict[str, Any]
    ) -> Tuple[ModelResponse, Dict[str, Any]]:
        model_response, tool_use = super()._parse_provider_response_delta(stream_event, assistant_message, tool_use)
        self._strip_redundant_provider_data(model_response)
        return model_response, tool_use
