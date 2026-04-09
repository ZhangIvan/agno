"""Qiniu Cloud Storage backend for page images.

Requirements:
    pip install qiniu
"""

import time
from dataclasses import dataclass, field
from typing import Optional

from agno.knowledge.storage.base import PageImageStorage
from agno.knowledge.storage.exceptions import OSSDeleteError, OSSUploadError
from agno.utils.log import log_debug


@dataclass
class QiniuStorage(PageImageStorage):
    """Qiniu Cloud Storage backend.

    Example::

        storage = QiniuStorage(
            access_key="...",
            secret_key="...",
            bucket_name="my-bucket",
            domain="https://cdn.example.com",
        )
    """

    access_key: str = ""
    secret_key: str = ""
    bucket_name: str = ""
    # CDN domain bound to the bucket (required for Qiniu)
    domain: str = ""
    # Optional key prefix prepended to every object key
    key_prefix: str = ""
    # Whether the bucket is private (requires signed URLs for access)
    is_private: bool = field(default=True, repr=False)

    def _get_auth(self):
        try:
            from qiniu import Auth
        except ImportError:
            raise ImportError("`qiniu` not installed. Run: pip install qiniu")
        return Auth(self.access_key, self.secret_key)

    def _get_bucket_manager(self):
        try:
            from qiniu import BucketManager
        except ImportError:
            raise ImportError("`qiniu` not installed. Run: pip install qiniu")
        return BucketManager(self._get_auth())

    def _get_domain(self) -> str:
        if not self.domain:
            raise ValueError("Qiniu requires a `domain` (CDN domain) to be configured")
        domain = self.domain.rstrip("/")
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        return domain

    def _full_key(self, object_key: str) -> str:
        return f"{self.key_prefix}{object_key}" if self.key_prefix else object_key

    def _base_url(self, object_key: str) -> str:
        return f"{self._get_domain()}/{object_key}"

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload(self, local_path: str, object_key: str, content_type: Optional[str] = None) -> str:
        try:
            from qiniu import put_file
        except ImportError:
            raise ImportError("`qiniu` not installed. Run: pip install qiniu")
        key = self._full_key(object_key)
        ct = content_type or self._infer_content_type(local_path) or "application/octet-stream"
        log_debug(f"Qiniu upload: {local_path} -> {self.bucket_name}/{key} (content-type: {ct})")

        def _do_upload():
            auth = self._get_auth()
            token = auth.upload_token(self.bucket_name, key)
            ret, info = put_file(token, key, local_path, mime_type=ct)
            if info.status_code != 200:
                raise OSSUploadError(f"Qiniu upload returned non-200: status={info.status_code}, {info}")
            return self._base_url(key)

        try:
            return self._with_retry(_do_upload, label=f"upload {self.bucket_name}/{key}")
        except OSSUploadError:
            raise
        except Exception as e:
            raise OSSUploadError(f"Qiniu upload failed: key={key}, file={local_path}, error={e}") from e

    def upload_bytes(self, data: bytes, object_key: str, content_type: Optional[str] = None) -> str:
        try:
            from qiniu import put_data
        except ImportError:
            raise ImportError("`qiniu` not installed. Run: pip install qiniu")
        key = self._full_key(object_key)
        ct = content_type or self.guess_content_type(key) or "application/octet-stream"
        log_debug(f"Qiniu upload_bytes: {len(data)} bytes -> {self.bucket_name}/{key}")

        def _do_upload():
            auth = self._get_auth()
            token = auth.upload_token(self.bucket_name, key)
            ret, info = put_data(token, key, data, mime_type=ct)
            if info.status_code != 200:
                raise OSSUploadError(f"Qiniu upload_bytes returned non-200: status={info.status_code}, {info}")
            return self._base_url(key)

        try:
            return self._with_retry(_do_upload, label=f"upload_bytes {self.bucket_name}/{key}")
        except OSSUploadError:
            raise
        except Exception as e:
            raise OSSUploadError(f"Qiniu upload_bytes failed: key={key}, error={e}") from e

    # ------------------------------------------------------------------
    # URL / signing
    # ------------------------------------------------------------------

    def sign_url(self, base_url: str, expires: int = 3600) -> str:
        """Convert a stored base URL to a signed temporary URL.

        Public mode: returns the original URL.
        Non-OSS URLs: returned unchanged.
        """
        if not self.is_private:
            return base_url
        key = self.extract_key_from_url(base_url)
        if key is None:
            return base_url
        return self.get_signed_url(key, expires)

    def get_signed_url(self, key: str, expires: int = 3600) -> str:
        log_debug(f"Qiniu get_signed_url: {key}  expires={expires}s")
        auth = self._get_auth()
        deadline = int(time.time()) + expires
        base_url = f"{self._get_domain()}/{key}"
        return auth.private_download_url(base_url, expires=deadline)

    def get_download_url(self, key: str, filename: str = "", expires: int = 3600) -> str:
        """Return a signed URL that triggers browser download via attname parameter."""
        if not filename:
            filename = key.rsplit("/", 1)[-1] if "/" in key else key
        from urllib.parse import quote

        base_url = f"{self._get_domain()}/{key}?attname={quote(filename)}"
        if self.is_private:
            auth = self._get_auth()
            deadline = int(time.time()) + expires
            return auth.private_download_url(base_url, expires=deadline)
        return base_url

    # ------------------------------------------------------------------
    # Object management
    # ------------------------------------------------------------------

    def delete(self, object_key: str) -> bool:
        key = self._full_key(object_key)
        log_debug(f"Qiniu delete: {self.bucket_name}/{key}")
        try:
            bucket_manager = self._get_bucket_manager()
            ret, info = bucket_manager.delete(self.bucket_name, key)
            return info.status_code in (200, 612)  # 612 = already deleted
        except Exception as e:
            raise OSSDeleteError(f"Qiniu delete failed: key={key}, error={e}") from e

    def exists(self, object_key: str) -> bool:
        key = self._full_key(object_key)
        bucket_manager = self._get_bucket_manager()
        ret, info = bucket_manager.stat(self.bucket_name, key)
        return info.status_code == 200

    # ------------------------------------------------------------------
    # Key / URL utilities
    # ------------------------------------------------------------------

    def extract_key_from_url(self, url: str) -> Optional[str]:
        """Extract object key from URL using the configured domain."""
        domain = self._get_domain().rstrip("/")
        for proto in ["https://", "http://"]:
            prefix = f"{proto}{self._strip_protocol(domain)}/"
            if url.startswith(prefix):
                return url[len(prefix) :].split("?")[0]
        # Also try with the domain as-is
        if url.startswith(domain + "/"):
            return url[len(domain) + 1 :].split("?")[0]
        return None

    def _key_from_url(self, base_url: str) -> str:
        """Legacy helper — delegates to ``extract_key_from_url`` with a fallback."""
        key = self.extract_key_from_url(base_url)
        if key is not None:
            return key
        return base_url.split("?")[0].rsplit("/", 1)[-1]
