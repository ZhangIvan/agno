"""Doubao (Volcano Engine / ByteDance Ark) multimodal embedding support.

Supports the doubao-embedding-vision series:
  - doubao-embedding-vision-241215  (3072-dim, text + image, no dimensions param)
  - doubao-embedding-vision-250328  (2048-dim max, text + image)
  - doubao-embedding-vision-250615  (text + image + video, sparse embedding)
  - doubao-embedding-vision-251215  (text + image + video, sparse embedding, instructions)

Reference: https://www.volcengine.com/docs/82379/1409291

Requirements:
    pip install volcenginesdkarkruntime
"""

import asyncio
import base64
import mimetypes
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from agno.knowledge.embedder.base import Embedder
from agno.utils.log import log_debug, log_error, log_warning


@dataclass
class DoubaoEmbedder(Embedder):
    """Embedder using ByteDance Volcano Engine Doubao-embedding-vision multimodal model.

    Both text and image inputs go through the same multimodal_embeddings.create() API.

    Example::

        from agno.knowledge.embedder.doubao import DoubaoEmbedder

        embedder = DoubaoEmbedder(
            id="doubao-embedding-vision-251215",
            dimensions=1024,
        )
        # Text embedding
        vec = embedder.get_embedding("what is the weather today?")
        # Image embedding (local file)
        vec = embedder.get_image_embedding("/path/to/page_1.png")
    """

    # Model ID, e.g. "doubao-embedding-vision-251215"
    id: str = "doubao-embedding-vision-251215"
    # Output dimensions (only supported by 250615 and later; set None to use model default)
    dimensions: Optional[int] = None
    # Encoding format
    encoding_format: str = "float"
    # ARK API key — defaults to ARK_API_KEY env var
    api_key: Optional[str] = None
    # Base URL for Ark platform (default is the official endpoint)
    base_url: Optional[str] = None
    # Optional instructions field (only supported by 251215 and later)
    # Used to guide the model toward a specific retrieval task.
    instructions: Optional[str] = None
    # Extra params forwarded to the API call
    request_params: Optional[Dict[str, Any]] = field(default=None)

    # ------------------------------------------------------------------ #
    # Private helpers                                                       #
    # ------------------------------------------------------------------ #

    def _get_api_key(self) -> str:
        key = self.api_key or os.environ.get("ARK_API_KEY") or os.environ.get("DOUBAO_API_KEY")
        if not key:
            raise ValueError(
                "Doubao API key not found. Set ARK_API_KEY environment variable "
                "or pass api_key= to DoubaoEmbedder."
            )
        return key

    def _sync_client(self):
        try:
            from volcenginesdkarkruntime import Ark
        except ImportError:
            raise ImportError(
                "`volcenginesdkarkruntime` not installed. "
                "Please install it via `pip install volcenginesdkarkruntime`."
            )
        params: Dict[str, Any] = {"api_key": self._get_api_key()}
        if self.base_url:
            params["base_url"] = self.base_url
        return Ark(**params)

    def _async_client(self):
        try:
            from volcenginesdkarkruntime import AsyncArk
        except ImportError:
            raise ImportError(
                "`volcenginesdkarkruntime` not installed. "
                "Please install it via `pip install volcenginesdkarkruntime`."
            )
        params: Dict[str, Any] = {"api_key": self._get_api_key()}
        if self.base_url:
            params["base_url"] = self.base_url
        return AsyncArk(**params)

    @staticmethod
    def _file_path_to_image_url(image_path: str) -> str:
        """Convert a local file path to a base64 data URI suitable for the API."""
        if image_path.startswith("data:") or image_path.startswith("http"):
            return image_path
        mime_type, _ = mimetypes.guess_type(image_path)
        mime_type = mime_type or "image/png"
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _build_call_kwargs(self, input_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build keyword arguments for multimodal_embeddings.create()."""
        kwargs: Dict[str, Any] = {
            "model": self.id,
            "encoding_format": self.encoding_format,
            "input": input_items,
        }
        if self.dimensions is not None:
            kwargs["dimensions"] = self.dimensions
        if self.instructions is not None:
            kwargs["instructions"] = self.instructions
        if self.request_params:
            kwargs.update(self.request_params)
        return kwargs

    @staticmethod
    def _extract_embedding(response: Any) -> List[float]:
        """Extract the embedding vector from the API response."""
        # response.data.embedding is a flat List[float]
        data = response.data
        if hasattr(data, "embedding"):
            return list(data.embedding)
        raise ValueError(f"Unexpected Doubao embedding response format: {response}")

    # ------------------------------------------------------------------ #
    # Text embedding                                                        #
    # ------------------------------------------------------------------ #

    def get_embedding(self, text: str) -> List[float]:
        client = self._sync_client()
        input_items = [{"type": "text", "text": text}]
        kwargs = self._build_call_kwargs(input_items)
        log_debug(f"DoubaoEmbedder text embed, model={self.id}")
        try:
            response = client.multimodal_embeddings.create(**kwargs)
            return self._extract_embedding(response)
        except Exception as e:
            log_error(f"DoubaoEmbedder.get_embedding failed: {e}")
            raise

    def get_embedding_and_usage(self, text: str) -> Tuple[List[float], Optional[Dict]]:
        client = self._sync_client()
        input_items = [{"type": "text", "text": text}]
        kwargs = self._build_call_kwargs(input_items)
        log_debug(f"DoubaoEmbedder text embed+usage, model={self.id}")
        try:
            response = client.multimodal_embeddings.create(**kwargs)
            embedding = self._extract_embedding(response)
            usage = None
            if hasattr(response, "usage") and response.usage is not None:
                u = response.usage
                usage = {
                    "prompt_tokens": u.get("prompt_tokens") if isinstance(u, dict) else getattr(u, "prompt_tokens", None),
                    "total_tokens": u.get("total_tokens") if isinstance(u, dict) else getattr(u, "total_tokens", None),
                    "prompt_tokens_details": u.get("prompt_tokens_details") if isinstance(u, dict) else getattr(u, "prompt_tokens_details", None),
                }
            return embedding, usage
        except Exception as e:
            log_error(f"DoubaoEmbedder.get_embedding_and_usage failed: {e}")
            raise

    async def async_get_embedding(self, text: str) -> List[float]:
        aclient = self._async_client()
        input_items = [{"type": "text", "text": text}]
        kwargs = self._build_call_kwargs(input_items)
        log_debug(f"DoubaoEmbedder async text embed, model={self.id}")
        try:
            async with aclient as client:
                response = await client.multimodal_embeddings.create(**kwargs)
            return self._extract_embedding(response)
        except Exception as e:
            log_error(f"DoubaoEmbedder.async_get_embedding failed: {e}")
            raise

    async def async_get_embedding_and_usage(self, text: str) -> Tuple[List[float], Optional[Dict]]:
        aclient = self._async_client()
        input_items = [{"type": "text", "text": text}]
        kwargs = self._build_call_kwargs(input_items)
        log_debug(f"DoubaoEmbedder async text embed+usage, model={self.id}")
        try:
            async with aclient as client:
                response = await client.multimodal_embeddings.create(**kwargs)
            embedding = self._extract_embedding(response)
            usage = None
            if hasattr(response, "usage") and response.usage is not None:
                u = response.usage
                usage = {
                    "prompt_tokens": u.get("prompt_tokens") if isinstance(u, dict) else getattr(u, "prompt_tokens", None),
                    "total_tokens": u.get("total_tokens") if isinstance(u, dict) else getattr(u, "total_tokens", None),
                    "prompt_tokens_details": u.get("prompt_tokens_details") if isinstance(u, dict) else getattr(u, "prompt_tokens_details", None),
                }
            return embedding, usage
        except Exception as e:
            log_error(f"DoubaoEmbedder.async_get_embedding_and_usage failed: {e}")
            raise

    # ------------------------------------------------------------------ #
    # Image embedding                                                       #
    # ------------------------------------------------------------------ #

    def get_image_embedding(self, image_path: str) -> Optional[List[float]]:
        """Get embedding for an image (local file path, URL, or base64 data URI).

        Args:
            image_path: Local file path, remote URL, or base64 data URI.

        Returns:
            Embedding vector as List[float], or None on failure.
        """
        try:
            image_url = self._file_path_to_image_url(image_path)
            client = self._sync_client()
            input_items = [{"type": "image_url", "image_url": {"url": image_url}}]
            kwargs = self._build_call_kwargs(input_items)
            log_debug(f"DoubaoEmbedder image embed, model={self.id}, path={image_path}")
            response = client.multimodal_embeddings.create(**kwargs)
            return self._extract_embedding(response)
        except Exception as e:
            log_warning(f"DoubaoEmbedder.get_image_embedding failed for {image_path}: {e}")
            return None

    def get_image_embedding_and_usage(self, image_path: str) -> Tuple[Optional[List[float]], Optional[Dict]]:
        """Get image embedding and token usage."""
        try:
            image_url = self._file_path_to_image_url(image_path)
            client = self._sync_client()
            input_items = [{"type": "image_url", "image_url": {"url": image_url}}]
            kwargs = self._build_call_kwargs(input_items)
            log_debug(f"DoubaoEmbedder image embed+usage, model={self.id}, path={image_path}")
            response = client.multimodal_embeddings.create(**kwargs)
            embedding = self._extract_embedding(response)
            usage = None
            if hasattr(response, "usage") and response.usage is not None:
                u = response.usage
                usage = {
                    "prompt_tokens": u.get("prompt_tokens") if isinstance(u, dict) else getattr(u, "prompt_tokens", None),
                    "total_tokens": u.get("total_tokens") if isinstance(u, dict) else getattr(u, "total_tokens", None),
                    "prompt_tokens_details": u.get("prompt_tokens_details") if isinstance(u, dict) else getattr(u, "prompt_tokens_details", None),
                }
            return embedding, usage
        except Exception as e:
            log_warning(f"DoubaoEmbedder.get_image_embedding_and_usage failed for {image_path}: {e}")
            return None, None

    async def async_get_image_embedding(self, image_path: str) -> Optional[List[float]]:
        """Async version of get_image_embedding."""
        try:
            # File I/O (base64 encoding) in a thread to avoid blocking the event loop
            image_url = await asyncio.to_thread(self._file_path_to_image_url, image_path)
            aclient = self._async_client()
            input_items = [{"type": "image_url", "image_url": {"url": image_url}}]
            kwargs = self._build_call_kwargs(input_items)
            log_debug(f"DoubaoEmbedder async image embed, model={self.id}, path={image_path}")
            async with aclient as client:
                response = await client.multimodal_embeddings.create(**kwargs)
            return self._extract_embedding(response)
        except Exception as e:
            log_warning(f"DoubaoEmbedder.async_get_image_embedding failed for {image_path}: {e}")
            return None

    async def async_get_image_embedding_and_usage(self, image_path: str) -> Tuple[Optional[List[float]], Optional[Dict]]:
        """Async get image embedding and token usage."""
        try:
            image_url = await asyncio.to_thread(self._file_path_to_image_url, image_path)
            aclient = self._async_client()
            input_items = [{"type": "image_url", "image_url": {"url": image_url}}]
            kwargs = self._build_call_kwargs(input_items)
            log_debug(f"DoubaoEmbedder async image embed+usage, model={self.id}, path={image_path}")
            async with aclient as client:
                response = await client.multimodal_embeddings.create(**kwargs)
            embedding = self._extract_embedding(response)
            usage = None
            if hasattr(response, "usage") and response.usage is not None:
                u = response.usage
                usage = {
                    "prompt_tokens": u.get("prompt_tokens") if isinstance(u, dict) else getattr(u, "prompt_tokens", None),
                    "total_tokens": u.get("total_tokens") if isinstance(u, dict) else getattr(u, "total_tokens", None),
                    "prompt_tokens_details": u.get("prompt_tokens_details") if isinstance(u, dict) else getattr(u, "prompt_tokens_details", None),
                }
            return embedding, usage
        except Exception as e:
            log_warning(f"DoubaoEmbedder.async_get_image_embedding_and_usage failed for {image_path}: {e}")
            return None, None
