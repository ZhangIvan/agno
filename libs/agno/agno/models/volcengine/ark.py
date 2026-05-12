import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel

from agno.exceptions import ModelAuthenticationError
from agno.models.message import Message
from agno.models.metrics import MessageMetrics
from agno.models.openai.like import OpenAILike
from agno.models.response import ModelResponse
from agno.models.volcengine._tools import inject_builtin_tools
from agno.run.agent import RunOutput
from agno.run.team import TeamRunOutput
from agno.utils.log import log_warning

try:
    from volcenginesdkarkruntime import Ark as ArkClient
    from volcenginesdkarkruntime import AsyncArk as AsyncArkClient
    from volcenginesdkarkruntime.types.chat import ChatCompletion, ChatCompletionChunk
except (ImportError, ModuleNotFoundError):
    raise ImportError(
        "`volcenginesdkarkruntime` not installed. Please install it via `pip install volcenginesdkarkruntime`."
    )


@dataclass
class Ark(OpenAILike):
    """Volcengine Ark (Doubao) chat model.

    Uses the ``volcenginesdkarkruntime`` SDK (a fork of the OpenAI SDK) to
    call ByteDance's Doubao models through the Volcengine Ark platform.

    Authentication (pick one):
      * API key  — set ``ARK_API_KEY`` (or ``DOUBAO_API_KEY``) or pass ``api_key=``.
      * AK / SK  — set ``VOLC_ACCESSKEY`` / ``VOLC_SECRETKEY`` or pass ``ak=`` / ``sk=``.

    Context caching:
      * ``caching`` — pass ``{"type": "enabled"}`` to enable Volcengine context
        caching via ``extra_body``.  Note: the Chat Completions API may not
        support this parameter; prefer ``VolcengineResponses`` for caching.

    Example::

        from agno.models.volcengine import Ark
        model = Ark(id="doubao-pro-32k", api_key="your-ark-api-key")
    """

    id: str = "doubao-pro-32k"
    name: str = "Volcengine"
    provider: str = "Volcengine"

    api_key: Optional[str] = field(default_factory=lambda: os.getenv("ARK_API_KEY"))
    base_url: str = "https://ark.cn-beijing.volces.com/api/v3"

    # AK/SK authentication
    ak: Optional[str] = field(default_factory=lambda: os.getenv("VOLC_ACCESSKEY"))
    sk: Optional[str] = field(default_factory=lambda: os.getenv("VOLC_SECRETKEY"))
    region: Optional[str] = None

    # E2E encryption — SDK auto-encrypts/decrypts when enabled
    enable_encryption: bool = False
    encryption_cert_path: Optional[str] = None
    # STS token — auto-managed by SDK when ak/sk are provided
    sts_token: Optional[str] = None

    # Volcengine-specific request parameters (pass-through)
    thinking: Optional[Dict[str, Any]] = None
    reasoning_effort: Optional[str] = None
    repetition_penalty: Optional[float] = None
    caching: Optional[Dict[str, Any]] = None

    # Volcengine built-in tools (Chat & Responses API)
    web_search: bool = False
    image_process: bool = False
    knowledge_search: Optional[Dict[str, Any]] = None
    mcp_servers: Optional[List[Dict[str, Any]]] = None

    # Override parent field types — Ark uses its own SDK client types
    client: Optional[ArkClient] = None  # type: ignore[assignment]
    async_client: Optional[AsyncArkClient] = None  # type: ignore[assignment]

    # ------------------------------------------- #
    # Client management                            #
    # ------------------------------------------- #

    def _get_client_params(self) -> Dict[str, Any]:
        if not self.api_key:
            self.api_key = os.getenv("ARK_API_KEY") or os.getenv("DOUBAO_API_KEY")
        if not self.api_key and not (self.ak and self.sk):
            self.ak = self.ak or os.getenv("VOLC_ACCESSKEY")
            self.sk = self.sk or os.getenv("VOLC_SECRETKEY")
            if not (self.ak and self.sk):
                raise ModelAuthenticationError(
                    message="ARK_API_KEY (or DOUBAO_API_KEY) not set. "
                    "Alternatively, set VOLC_ACCESSKEY and VOLC_SECRETKEY.",
                    model_name=self.name,
                )

        params: Dict[str, Any] = {
            "base_url": self.base_url,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }
        if self.api_key:
            params["api_key"] = self.api_key
        if self.ak:
            params["ak"] = self.ak
        if self.sk:
            params["sk"] = self.sk
        if self.region:
            params["region"] = self.region
        if self.client_params:
            params.update(self.client_params)
        return params

    def _apply_encryption_config(self) -> None:
        """Apply E2E encryption config before client creation.

        The Ark SDK reads ``E2E_CERTIFICATE_PATH`` from the environment when
        the certificate manager is first initialised.
        """
        if self.encryption_cert_path:
            os.environ["E2E_CERTIFICATE_PATH"] = self.encryption_cert_path

    def get_client(self) -> ArkClient:
        if self.client is not None and not self.client.is_closed():
            return self.client

        self._apply_encryption_config()
        client_params = self._get_client_params()
        if self.http_client is not None:
            client_params["http_client"] = self.http_client

        self.client = ArkClient(**client_params)
        return self.client

    def get_async_client(self) -> AsyncArkClient:
        if self.async_client is not None and not self.async_client.is_closed():
            return self.async_client

        self._apply_encryption_config()

        client_params = self._get_client_params()
        if self.http_client is not None:
            client_params["http_client"] = self.http_client

        self.async_client = AsyncArkClient(**client_params)
        return self.async_client

    # ------------------------------------------- #
    # Request building                             #
    # ------------------------------------------- #

    def get_request_params(  # type: ignore[override]
        self,
        response_format: Optional[Union[Dict, Type[BaseModel]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        run_response: Optional[Union[RunOutput, TeamRunOutput]] = None,
    ) -> Dict[str, Any]:
        params = super().get_request_params(
            response_format=response_format,
            tools=tools,
            tool_choice=tool_choice,
            run_response=run_response,
        )

        if self.thinking is not None:
            params["thinking"] = self.thinking
        if self.reasoning_effort is not None:
            params["reasoning_effort"] = self.reasoning_effort
        if self.repetition_penalty is not None:
            params["repetition_penalty"] = self.repetition_penalty

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

    def _format_message(self, message: Message, compress_tool_results: bool = False) -> Dict[str, Any]:
        msg_dict = super()._format_message(message, compress_tool_results=compress_tool_results)
        if message.reasoning_content is not None:
            msg_dict["reasoning_content"] = message.reasoning_content
        return msg_dict

    # ------------------------------------------- #
    # Response parsing                             #
    # ------------------------------------------- #

    def _parse_provider_response(
        self,
        response: ChatCompletion,
        response_format: Optional[Union[Dict, Type[BaseModel]]] = None,
    ) -> ModelResponse:
        model_response = ModelResponse()
        response_message = response.choices[0].message

        if response_message.role is not None:
            model_response.role = response_message.role

        if hasattr(response_message, "reasoning_content") and response_message.reasoning_content is not None:
            model_response.reasoning_content = response_message.reasoning_content
            if response_message.content is not None:
                model_response.content = response_message.content
        elif response_message.content is not None:
            model_response.content = response_message.content
            if model_response.content:
                from agno.utils.reasoning import extract_thinking_content

                reasoning_content, output_content = extract_thinking_content(model_response.content)
                if reasoning_content:
                    model_response.reasoning_content = reasoning_content
                    model_response.content = output_content

        if response_message.tool_calls is not None and len(response_message.tool_calls) > 0:
            try:
                model_response.tool_calls = [t.model_dump() for t in response_message.tool_calls]
            except Exception as e:
                log_warning(f"Error processing tool calls: {str(e)}")

        if response.usage is not None:
            model_response.response_usage = self._get_metrics(response.usage)

        model_response.provider_data = {}
        if response.id:
            model_response.provider_data["id"] = response.id
        if hasattr(response, "model_extra") and response.model_extra:
            model_response.provider_data["model_extra"] = response.model_extra
        if hasattr(response.choices[0], "moderation_hit_type") and response.choices[0].moderation_hit_type:
            model_response.provider_data["moderation_hit_type"] = response.choices[0].moderation_hit_type

        return model_response

    def _parse_provider_response_delta(self, response_delta: ChatCompletionChunk) -> ModelResponse:
        model_response = ModelResponse()

        if response_delta.choices and len(response_delta.choices) > 0:
            choice_delta = response_delta.choices[0].delta
            if choice_delta:
                if choice_delta.content is not None:
                    model_response.content = choice_delta.content
                    if model_response.provider_data is None:
                        model_response.provider_data = {}
                    if response_delta.id:
                        model_response.provider_data["id"] = response_delta.id
                    if hasattr(response_delta, "model_extra") and response_delta.model_extra:
                        model_response.provider_data["model_extra"] = response_delta.model_extra

                if choice_delta.tool_calls is not None:
                    model_response.tool_calls = choice_delta.tool_calls  # type: ignore

                if hasattr(choice_delta, "reasoning_content") and choice_delta.reasoning_content is not None:
                    model_response.reasoning_content = choice_delta.reasoning_content

            if (
                hasattr(response_delta.choices[0], "moderation_hit_type")
                and response_delta.choices[0].moderation_hit_type
            ):
                if model_response.provider_data is None:
                    model_response.provider_data = {}
                model_response.provider_data["moderation_hit_type"] = response_delta.choices[0].moderation_hit_type

        if self._should_collect_metrics(response_delta) and response_delta.usage is not None:
            model_response.response_usage = self._get_metrics(response_delta.usage)

        return model_response

    # ------------------------------------------- #
    # Metrics                                      #
    # ------------------------------------------- #

    def _get_metrics(self, response_usage: Any) -> MessageMetrics:
        metrics = MessageMetrics()

        metrics.input_tokens = response_usage.prompt_tokens or 0
        metrics.output_tokens = response_usage.completion_tokens or 0
        metrics.total_tokens = response_usage.total_tokens or 0

        # Prompt token details — Ark has cached_tokens + provisioned_tokens (no audio_tokens)
        prompt_details = getattr(response_usage, "prompt_tokens_details", None)
        if prompt_details:
            metrics.cache_read_tokens = getattr(prompt_details, "cached_tokens", 0) or 0

        # Completion token details — Ark has reasoning_tokens + provisioned_tokens (no audio_tokens)
        completion_details = getattr(response_usage, "completion_tokens_details", None)
        if completion_details:
            metrics.reasoning_tokens = getattr(completion_details, "reasoning_tokens", 0) or 0

        metrics.cost = getattr(response_usage, "cost", None)

        return metrics
