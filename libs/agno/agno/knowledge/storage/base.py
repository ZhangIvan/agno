"""Abstract base class for page image cloud storage backends."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass


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
        signed = storage.sign_url(url, expires=3600)
    """

    @abstractmethod
    def upload(self, local_path: str, object_key: str) -> str:
        """Upload a local file and return its permanent base URL (no signature).

        Args:
            local_path: Path to the local PNG file.
            object_key: Key (path) inside the bucket, e.g. ``"docs/file/page_1.png"``.

        Returns:
            Permanent HTTPS URL without a signature.
        """

    @abstractmethod
    def sign_url(self, base_url: str, expires: int = 3600) -> str:
        """Return a pre-signed URL valid for ``expires`` seconds.

        Args:
            base_url: The permanent URL returned by ``upload()``.
            expires: Validity in seconds (default 3600 = 1 hour).

        Returns:
            Pre-signed URL string.
        """

    async def async_upload(self, local_path: str, object_key: str) -> str:
        """Async wrapper around ``upload()``."""
        return await asyncio.to_thread(self.upload, local_path, object_key)

    async def async_sign_url(self, base_url: str, expires: int = 3600) -> str:
        """Async wrapper around ``sign_url()``."""
        return await asyncio.to_thread(self.sign_url, base_url, expires)
