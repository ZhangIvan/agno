"""Abstract base class for page image cloud storage backends."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from agno.utils.log import log_warning


@dataclass
class PageImageStorage(ABC):
    """Abstract storage backend for captured page images.

    Implementations upload PNG files produced by page capture and return
    permanent (unsigned) base URLs.  At retrieval time, ``sign_url()`` is
    called to generate short-lived pre-signed URLs that are forwarded to the
    vision LLM.

    Example::

        storage = AliyunOSSStorage(
            endpoint="oss-cn-hangzhou.aliyuncs.com",
            bucket_name="my-bucket",
            access_key_id="...",
            access_key_secret="...",
        )
        url = storage.upload("/tmp/page_1.png", "docs/report/page_1.png")
        signed = storage.sign_url(url, expires=7200)
    """

    @abstractmethod
    def upload(self, local_path: str, object_key: str, content_type: Optional[str] = None) -> str:
        """Upload a local file and return its permanent base URL (no signature).

        Args:
            local_path: Path to the local file.
            object_key: Key (path) inside the bucket, e.g. ``"docs/file/page_1.png"``.
            content_type: Optional MIME type. If not provided, will be inferred from file extension.

        Returns:
            Permanent HTTPS URL without a signature.
        """

    def _infer_content_type(self, file_path: str) -> str:
        """Infer content type from file extension.

        Args:
            file_path: Path to the file.

        Returns:
            MIME type string.
        """
        from agno.knowledge.utils import get_content_type

        return get_content_type(file_path)

    @abstractmethod
    def sign_url(self, base_url: str, expires: int = 3600) -> str:
        """Return a pre-signed URL valid for ``expires`` seconds.

        Args:
            base_url: The permanent URL returned by ``upload()``.
            expires: Validity in seconds (default 3600 = 1 hour).

        Returns:
            Pre-signed URL string.
        """

    async def async_upload(self, local_path: str, object_key: str, content_type: Optional[str] = None) -> str:
        """Async wrapper around ``upload()``."""
        return await asyncio.to_thread(self.upload, local_path, object_key, content_type)

    async def async_sign_url(self, base_url: str, expires: int = 3600) -> str:
        """Async wrapper around ``sign_url()``."""
        return await asyncio.to_thread(self.sign_url, base_url, expires)

    async def async_upload_with_retry(
        self,
        local_path: str,
        object_key: str,
        content_type: Optional[str] = None,
        max_retries: int = 3,
        backoff: float = 2.0,
    ) -> str:
        """Upload with exponential backoff retry on failure.

        Args:
            local_path: Path to the local file.
            object_key: Key (path) inside the bucket.
            content_type: Optional MIME type.
            max_retries: Maximum number of retry attempts (default 3).
            backoff: Base backoff factor for exponential delay (default 2.0).

        Returns:
            Permanent HTTPS URL without a signature.

        Raises:
            Exception: If all retry attempts fail.
        """
        last_exception: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                return await self.async_upload(local_path, object_key, content_type)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = backoff**attempt
                    log_warning(
                        f"Upload failed for {local_path} (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)

        raise last_exception
