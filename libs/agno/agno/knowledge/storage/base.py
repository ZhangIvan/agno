"""Abstract base class for page image cloud storage backends."""

import asyncio
import logging
import mimetypes
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional, TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class PageImageStorage(ABC):
    """Abstract storage backend for captured page images.

    Implementations upload files produced by page capture and return
    permanent (unsigned) base URLs.  At retrieval time, ``sign_url()`` is
    called to generate short-lived pre-signed URLs that are forwarded to the
    vision LLM.

    URL conventions:
        - ``upload()`` / ``upload_bytes()`` -> returns an unsigned URL for storage
        - ``sign_url(url)`` -> converts a stored URL to a signed temporary URL
        - ``get_signed_url(key)`` -> returns a signed URL from a key directly

    Retry:
        All upload and sign operations are wrapped with exponential-backoff
        retry controlled by ``max_retries`` and ``retry_base_delay``.

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

    is_private: bool = field(default=True, repr=False)
    custom_domain: str = field(default="", repr=False)
    # Retry configuration
    max_retries: int = field(default=3, repr=False)
    retry_base_delay: float = field(default=1.0, repr=False)

    # ------------------------------------------------------------------
    # Upload methods
    # ------------------------------------------------------------------

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

    @abstractmethod
    def upload_bytes(self, data: bytes, object_key: str, content_type: Optional[str] = None) -> str:
        """Upload bytes and return its permanent base URL (no signature).

        Args:
            data: Bytes to upload.
            object_key: Key (path) inside the bucket.
            content_type: Optional MIME type.

        Returns:
            Permanent HTTPS URL without a signature.
        """

    # ------------------------------------------------------------------
    # URL / signing methods
    # ------------------------------------------------------------------

    @abstractmethod
    def sign_url(self, base_url: str, expires: int = 3600) -> str:
        """Return a pre-signed URL valid for ``expires`` seconds.

        Public mode: returns the original URL unchanged.
        Private mode: extracts the key and generates a signed URL.
        Non-OSS URLs: returned unchanged.

        Args:
            base_url: The permanent URL returned by ``upload()``.
            expires: Validity in seconds (default 3600 = 1 hour).

        Returns:
            Pre-signed URL string.
        """

    @abstractmethod
    def get_signed_url(self, key: str, expires: int = 3600) -> str:
        """Return a signed URL from an object key directly.

        Args:
            key: Object key in the bucket.
            expires: Validity in seconds.

        Returns:
            Pre-signed URL string.
        """

    def get_download_url(self, key: str, filename: str = "", expires: int = 3600) -> str:
        """Return a signed URL that triggers a browser download.

        Default implementation delegates to ``get_signed_url()``.
        Subclasses can override to inject Content-Disposition headers.

        Args:
            key: Object key.
            filename: Download filename. Empty means derive from key.
            expires: Validity in seconds.
        """
        if not filename:
            filename = key.rsplit("/", 1)[-1] if "/" in key else key
        return self.get_signed_url(key, expires)

    # ------------------------------------------------------------------
    # Object management
    # ------------------------------------------------------------------

    @abstractmethod
    def delete(self, object_key: str) -> bool:
        """Delete an object from the bucket.

        Args:
            object_key: Key of the object to delete.

        Returns:
            True if deletion succeeded.

        Raises:
            OSSDeleteError: If the deletion fails.
        """

    @abstractmethod
    def exists(self, object_key: str) -> bool:
        """Check whether an object exists in the bucket.

        Args:
            object_key: Key of the object.

        Returns:
            True if the object exists.
        """

    # ------------------------------------------------------------------
    # Key / URL utilities
    # ------------------------------------------------------------------

    @abstractmethod
    def extract_key_from_url(self, url: str) -> Optional[str]:
        """Extract the object key from a full URL.

        Returns None if the URL does not belong to this storage backend.
        """

    # ------------------------------------------------------------------
    # Retry helper
    # ------------------------------------------------------------------

    def _with_retry(self, fn: Callable[[], T], label: str = "") -> T:
        """Execute *fn* with exponential-backoff retry.

        Retries up to ``self.max_retries`` times on any exception, waiting
        ``retry_base_delay * 2 ** attempt`` seconds between attempts.

        Args:
            fn: Zero-arg callable to execute.
            label: Human-readable label for log messages (e.g. "upload docs/x.png").

        Returns:
            The return value of *fn*.

        Raises:
            The last exception if all retries are exhausted.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                return fn()
            except Exception as e:
                last_exc = e
                if attempt < self.max_retries:
                    wait = self.retry_base_delay * (2**attempt)
                    log.warning(
                        "OSS operation failed (attempt %d/%d), retrying in %.1fs: %s  error=%s",
                        attempt + 1,
                        self.max_retries + 1,
                        wait,
                        label,
                        e,
                    )
                    time.sleep(wait)
        # All retries exhausted
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Async wrappers
    # ------------------------------------------------------------------

    async def async_upload(self, local_path: str, object_key: str, content_type: Optional[str] = None) -> str:
        """Async wrapper around ``upload()``."""
        return await asyncio.to_thread(self.upload, local_path, object_key, content_type)

    async def async_upload_bytes(self, data: bytes, object_key: str, content_type: Optional[str] = None) -> str:
        """Async wrapper around ``upload_bytes()``."""
        return await asyncio.to_thread(self.upload_bytes, data, object_key, content_type)

    async def async_sign_url(self, base_url: str, expires: int = 3600) -> str:
        """Async wrapper around ``sign_url()``."""
        return await asyncio.to_thread(self.sign_url, base_url, expires)

    async def async_delete(self, object_key: str) -> bool:
        """Async wrapper around ``delete()``."""
        return await asyncio.to_thread(self.delete, object_key)

    async def async_exists(self, object_key: str) -> bool:
        """Async wrapper around ``exists()``."""
        return await asyncio.to_thread(self.exists, object_key)

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def guess_content_type(key: str) -> Optional[str]:
        """Guess MIME type from a file key's extension."""
        content_type, _ = mimetypes.guess_type(key)
        return content_type

    def _infer_content_type(self, file_path: str) -> str:
        """Infer content type from file extension, falling back to ``application/octet-stream``."""
        from agno.knowledge.utils import get_content_type

        return get_content_type(file_path)

    @staticmethod
    def _strip_protocol(url: str) -> str:
        """Remove ``http://`` or ``https://`` prefix."""
        return url.replace("https://", "").replace("http://", "")

    @staticmethod
    def _ensure_protocol(host: str, default: str = "https") -> str:
        """Ensure host has a protocol prefix."""
        if host.startswith("http://") or host.startswith("https://"):
            return host
        return f"{default}://{host}"
