"""Aliyun OSS (Object Storage Service) backend for page images.

Requirements:
    pip install oss2
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from agno.knowledge.storage.base import PageImageStorage
from agno.knowledge.storage.exceptions import OSSDeleteError, OSSUploadError
from agno.utils.log import log_debug


@dataclass
class AliyunOSSStorage(PageImageStorage):
    """Aliyun OSS storage backend.

    Example::

        storage = AliyunOSSStorage(
            endpoint="oss-cn-hangzhou.aliyuncs.com",
            bucket_name="my-knowledge-bucket",
            access_key_id="LTAI...",
            access_key_secret="...",
        )
    """

    endpoint: str = ""
    bucket_name: str = ""
    access_key_id: str = ""
    access_key_secret: str = ""
    # Optional key prefix prepended to every object key, e.g. "knowledge/"
    key_prefix: str = ""
    # Optional custom domain for URL generation (overrides default bucket URL)
    custom_domain: str = field(default="", repr=False)
    # Whether the bucket is private (requires signed URLs for access)
    is_private: bool = field(default=True, repr=False)

    def _get_bucket(self):
        try:
            import oss2
        except ImportError:
            raise ImportError("`oss2` not installed. Run: pip install oss2")
        auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        return oss2.Bucket(auth, f"https://{self.endpoint}", self.bucket_name)

    def _full_key(self, object_key: str) -> str:
        return f"{self.key_prefix}{object_key}" if self.key_prefix else object_key

    def _base_url(self, object_key: str) -> str:
        if self.custom_domain:
            return f"{self._ensure_protocol(self.custom_domain)}/{object_key}"
        return f"https://{self.bucket_name}.{self.endpoint}/{object_key}"

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload(self, local_path: str, object_key: str, content_type: Optional[str] = None) -> str:
        key = self._full_key(object_key)
        ct = content_type or self._infer_content_type(local_path)
        log_debug(f"AliyunOSS upload: {local_path} -> {self.bucket_name}/{key} (content-type: {ct})")

        def _do_upload():
            headers = {"Content-Type": ct} if ct else None
            self._get_bucket().put_object_from_file(key, local_path, headers=headers)
            return self._base_url(key)

        try:
            return self._with_retry(_do_upload, label=f"upload {self.bucket_name}/{key}")
        except Exception as e:
            raise OSSUploadError(f"AliyunOSS upload failed: key={key}, file={local_path}, error={e}") from e

    def upload_bytes(self, data: bytes, object_key: str, content_type: Optional[str] = None) -> str:
        key = self._full_key(object_key)
        ct = content_type or self.guess_content_type(key) or "application/octet-stream"
        log_debug(f"AliyunOSS upload_bytes: {len(data)} bytes -> {self.bucket_name}/{key}")

        def _do_upload():
            headers = {"Content-Type": ct} if ct else None
            self._get_bucket().put_object(key, data, headers=headers)
            return self._base_url(key)

        try:
            return self._with_retry(_do_upload, label=f"upload_bytes {self.bucket_name}/{key}")
        except Exception as e:
            raise OSSUploadError(f"AliyunOSS upload_bytes failed: key={key}, error={e}") from e

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
        log_debug(f"AliyunOSS sign_url: {key}  expires={expires}s")
        return self._get_bucket().sign_url("GET", key, expires)

    def get_download_url(self, key: str, filename: str = "", expires: int = 3600) -> str:
        """Return a signed URL that triggers browser download via Content-Disposition."""
        if not filename:
            filename = key.rsplit("/", 1)[-1] if "/" in key else key
        disposition = f'attachment; filename="{filename}"'
        return self._get_bucket().sign_url(
            "GET", key, expires,
            params={"response-content-disposition": disposition},
        )

    # ------------------------------------------------------------------
    # Object management
    # ------------------------------------------------------------------

    def delete(self, object_key: str) -> bool:
        key = self._full_key(object_key)
        log_debug(f"AliyunOSS delete: {self.bucket_name}/{key}")
        try:
            self._get_bucket().delete_object(key)
            return True
        except Exception as e:
            raise OSSDeleteError(f"AliyunOSS delete failed: key={key}, error={e}") from e

    def exists(self, object_key: str) -> bool:
        key = self._full_key(object_key)
        return self._get_bucket().object_exists(key)

    # ------------------------------------------------------------------
    # Key / URL utilities
    # ------------------------------------------------------------------

    def extract_key_from_url(self, url: str) -> Optional[str]:
        """Extract the object key from a URL.

        Handles both standard bucket URLs and custom domain URLs,
        with both http and https protocols.
        """
        # Standard format: https://{bucket}.{endpoint}/{key}
        base = f"{self.bucket_name}.{self.endpoint}"
        for proto in ["https://", "http://"]:
            prefix = f"{proto}{base}/"
            if url.startswith(prefix):
                return url[len(prefix):].split("?")[0]

        # Custom domain format
        if self.custom_domain:
            domain_stripped = self._strip_protocol(self.custom_domain)
            for proto in ["https://", "http://"]:
                prefix = f"{proto}{domain_stripped}/"
                if url.startswith(prefix):
                    return url[len(prefix):].split("?")[0]

        return None

    def _key_from_url(self, base_url: str) -> str:
        """Legacy helper — delegates to ``extract_key_from_url`` with a fallback."""
        key = self.extract_key_from_url(base_url)
        if key is not None:
            return key
        # Fallback: strip query params and return last path component
        return base_url.split("?")[0].rsplit("/", 1)[-1]

    # ------------------------------------------------------------------
    # Upload credentials (frontend direct upload)
    # ------------------------------------------------------------------

    def get_upload_credentials(
        self,
        prefix: Optional[str] = None,
        expires: int = 3600,
        content_type: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate a presigned PUT URL for frontend direct upload."""
        object_key = self._generate_upload_object_key(prefix, **kwargs)
        key = self._full_key(object_key)

        bucket = self._get_bucket()
        headers = {"Content-Type": content_type} if content_type else {}
        upload_url = bucket.sign_url("PUT", key, expires, headers=headers)

        return self._build_credential_response(
            provider="aliyun_oss",
            upload_url=upload_url,
            object_key=key,
            content_type=content_type,
            expires_at=self._compute_expires_at(expires),
        )
