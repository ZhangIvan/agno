"""Aliyun OSS (Object Storage Service) backend for page images.

Requirements:
    pip install oss2
"""

from dataclasses import dataclass
from typing import Optional

from agno.knowledge.storage.base import PageImageStorage
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
        return f"https://{self.bucket_name}.{self.endpoint}/{object_key}"

    def _key_from_url(self, base_url: str) -> str:
        prefix = f"https://{self.bucket_name}.{self.endpoint}/"
        if base_url.startswith(prefix):
            return base_url[len(prefix):]
        # Fallback: strip query params and return last path component
        return base_url.split("?")[0].split("/", 3)[-1]

    def upload(self, local_path: str, object_key: str, content_type: Optional[str] = None) -> str:
        key = self._full_key(object_key)
        ct = content_type or self._infer_content_type(local_path)
        log_debug(f"AliyunOSS upload: {local_path} -> {self.bucket_name}/{key} (content-type: {ct})")
        self._get_bucket().put_object_from_file(key, local_path, headers={"Content-Type": ct})
        return self._base_url(key)

    def sign_url(self, base_url: str, expires: int = 3600) -> str:
        key = self._key_from_url(base_url)
        log_debug(f"AliyunOSS sign_url: {key}  expires={expires}s")
        return self._get_bucket().sign_url("GET", key, expires)
