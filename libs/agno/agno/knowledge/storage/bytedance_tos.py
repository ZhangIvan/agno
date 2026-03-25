"""ByteDance TOS (Tinder Object Storage / Volcano Engine) backend for page images.

Requirements:
    pip install tos
"""

from dataclasses import dataclass
from typing import Optional

from agno.knowledge.storage.base import PageImageStorage
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

    def _get_client(self):
        try:
            import tos
        except ImportError:
            raise ImportError("`tos` not installed. Run: pip install tos")
        return tos.TosClientV2(
            self.access_key,
            self.secret_key,
            self.endpoint,
            self.region,
            max_retry_count=3,
        )

    def _full_key(self, object_key: str) -> str:
        return f"{self.key_prefix}{object_key}" if self.key_prefix else object_key

    def _base_url(self, object_key: str) -> str:
        return f"https://{self.bucket_name}.{self.endpoint}/{object_key}"

    def _key_from_url(self, base_url: str) -> str:
        prefix = f"https://{self.bucket_name}.{self.endpoint}/"
        if base_url.startswith(prefix):
            return base_url[len(prefix) :].split("?")[0]
        return base_url.split("?")[0].split("/", 3)[-1]

    def upload(self, local_path: str, object_key: str, content_type: Optional[str] = None) -> str:
        key = self._full_key(object_key)
        ct = content_type or self._infer_content_type(local_path)
        log_debug(f"ByteDanceTOS upload: {local_path} -> {self.bucket_name}/{key} (content-type: {ct})")
        client = self._get_client()
        # TOS SDK put_object_from_file accepts headers parameter for content-type
        client.put_object_from_file(self.bucket_name, key, file_path=local_path, content_type=ct)
        return self._base_url(key)

    def sign_url(self, base_url: str, expires: int = 3600) -> str:
        key = self._key_from_url(base_url)
        log_debug(f"ByteDanceTOS sign_url: {key}  expires={expires}s")
        client = self._get_client()
        from tos.enum import HttpMethodType

        result = client.pre_signed_url(HttpMethodType.Http_Method_Get, self.bucket_name, key, expires=expires)
        return result.signed_url
