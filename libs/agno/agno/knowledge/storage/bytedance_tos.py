"""ByteDance TOS (Volcano Engine Object Storage) backend for page images.

Requirements:
    pip install tos
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

from agno.knowledge.storage.base import PageImageStorage
from agno.knowledge.storage.exceptions import OSSUploadError, OSSDeleteError
from agno.utils.log import log_debug


@dataclass
class ByteDanceTOSStorage(PageImageStorage):
    """ByteDance Volcano Engine TOS storage backend.

    Example::

        storage = ByteDanceTOSStorage(
            access_key="...",
            secret_key="...",
            endpoint="tos-cn-beijing.volces.com",
            region="cn-beijing",
            bucket_name="my-bucket",
        )
    """

    access_key: str = ""
    secret_key: str = ""
    endpoint: str = ""
    region: str = ""
    bucket_name: str = ""
    # Optional key prefix prepended to every object key
    key_prefix: str = ""
    # Optional custom domain for URL generation
    custom_domain: str = field(default="", repr=False)
    # Whether the bucket is private
    is_private: bool = field(default=True, repr=False)

    def _get_client(self):
        try:
            import tos
        except ImportError:
            raise ImportError("`tos` not installed. Run: pip install tos")
        return tos.TosClientV2(
            ak=self.access_key,
            sk=self.secret_key,
            endpoint=self._strip_protocol(self.endpoint),
            region=self.region,
            max_retry_count=3,
        )

    def _full_key(self, object_key: str) -> str:
        return f"{self.key_prefix}{object_key}" if self.key_prefix else object_key

    def _base_url(self, object_key: str) -> str:
        if self.custom_domain:
            return f"{self._ensure_protocol(self.custom_domain)}/{object_key}"
        return f"https://{self.bucket_name}.{self._strip_protocol(self.endpoint)}/{object_key}"

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload(self, local_path: str, object_key: str, content_type: Optional[str] = None) -> str:
        key = self._full_key(object_key)
        ct = content_type or self._infer_content_type(local_path)
        log_debug(f"ByteDanceTOS upload: {local_path} -> {self.bucket_name}/{key} (content-type: {ct})")

        def _do_upload():
            client = self._get_client()
            client.put_object_from_file(self.bucket_name, key, file_path=local_path, content_type=ct)
            return self._base_url(key)

        try:
            return self._with_retry(_do_upload, label=f"upload {self.bucket_name}/{key}")
        except Exception as e:
            raise OSSUploadError(f"ByteDanceTOS upload failed: key={key}, file={local_path}, error={e}") from e

    def upload_bytes(self, data: bytes, object_key: str, content_type: Optional[str] = None) -> str:
        key = self._full_key(object_key)
        ct = content_type or self.guess_content_type(key) or "application/octet-stream"
        log_debug(f"ByteDanceTOS upload_bytes: {len(data)} bytes -> {self.bucket_name}/{key}")

        def _do_upload():
            client = self._get_client()
            client.put_object(self.bucket_name, key, content=data, content_type=ct)
            return self._base_url(key)

        try:
            return self._with_retry(_do_upload, label=f"upload_bytes {self.bucket_name}/{key}")
        except Exception as e:
            raise OSSUploadError(f"ByteDanceTOS upload_bytes failed: key={key}, error={e}") from e

    # ------------------------------------------------------------------
    # URL / signing
    # ------------------------------------------------------------------

    def sign_url(self, base_url: str, expires: int = 3600) -> str:
        """Convert a stored base URL to a signed temporary URL."""
        if not self.is_private:
            return base_url
        key = self.extract_key_from_url(base_url)
        if key is None:
            return base_url
        return self.get_signed_url(key, expires)

    def get_signed_url(self, key: str, expires: int = 3600, header: Optional[Dict] = None, query: Optional[Dict] = None) -> str:
        log_debug(f"ByteDanceTOS sign_url: {key}  expires={expires}s")
        try:
            from tos.enum import HttpMethodType

            client = self._get_client()
            result = client.pre_signed_url(
                http_method=HttpMethodType.Http_Method_Get,
                bucket=self.bucket_name,
                key=key,
                expires=expires,
                header=header,
                query=query,
            )
            return result.signed_url
        except Exception as e:
            log_debug(f"ByteDanceTOS sign_url failed, falling back to base URL: key={key}, error={e}", exc_info=True)
            return self._base_url(key)

    def get_download_url(self, key: str, filename: str = "", expires: int = 3600) -> str:
        """Return a signed URL that triggers browser download via response-content-disposition."""
        if not filename:
            filename = key.rsplit("/", 1)[-1] if "/" in key else key
        query = {"response-content-disposition": f'attachment; filename="{filename}"'}
        return self.get_signed_url(key, expires, query=query)

    # ------------------------------------------------------------------
    # Object management
    # ------------------------------------------------------------------

    def delete(self, object_key: str) -> bool:
        key = self._full_key(object_key)
        log_debug(f"ByteDanceTOS delete: {self.bucket_name}/{key}")
        try:
            client = self._get_client()
            client.delete_object(bucket=self.bucket_name, key=key)
            return True
        except Exception as e:
            raise OSSDeleteError(f"ByteDanceTOS delete failed: key={key}, error={e}") from e

    def exists(self, object_key: str) -> bool:
        key = self._full_key(object_key)
        try:
            client = self._get_client()
            client.head_object(bucket=self.bucket_name, key=key)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Key / URL utilities
    # ------------------------------------------------------------------

    def extract_key_from_url(self, url: str) -> Optional[str]:
        """Extract object key from URL."""
        # Custom domain format
        if self.custom_domain:
            domain_stripped = self._strip_protocol(self.custom_domain)
            for proto in ["https://", "http://"]:
                prefix = f"{proto}{domain_stripped}/"
                if url.startswith(prefix):
                    return url[len(prefix):].split("?")[0]

        # Standard format: https://{bucket}.{endpoint}/{key}
        base = f"{self.bucket_name}.{self._strip_protocol(self.endpoint)}"
        for proto in ["https://", "http://"]:
            prefix = f"{proto}{base}/"
            if url.startswith(prefix):
                return url[len(prefix):].split("?")[0]

        return None

    def _key_from_url(self, base_url: str) -> str:
        """Legacy helper — delegates to ``extract_key_from_url`` with a fallback."""
        key = self.extract_key_from_url(base_url)
        if key is not None:
            return key
        return base_url.split("?")[0].split("/", 3)[-1]
