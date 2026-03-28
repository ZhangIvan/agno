"""Qiniu Cloud Storage backend for page images.

Requirements:
    pip install qiniu
"""

import time
from dataclasses import dataclass
from typing import Optional

from agno.knowledge.storage.base import PageImageStorage
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
    # Public or private CDN domain bound to the bucket
    domain: str = ""
    # Optional key prefix prepended to every object key
    key_prefix: str = ""

    def _get_auth(self):
        try:
            from qiniu import Auth
        except ImportError:
            raise ImportError("`qiniu` not installed. Run: pip install qiniu")
        return Auth(self.access_key, self.secret_key)

    def _full_key(self, object_key: str) -> str:
        return f"{self.key_prefix}{object_key}" if self.key_prefix else object_key

    def _base_url(self, object_key: str) -> str:
        domain = self.domain.rstrip("/")
        return f"{domain}/{object_key}"

    def _key_from_url(self, base_url: str) -> str:
        domain = self.domain.rstrip("/")
        if base_url.startswith(domain + "/"):
            return base_url[len(domain) + 1 :].split("?")[0]
        return base_url.split("?")[0].rsplit("/", 1)[-1]

    def upload(self, local_path: str, object_key: str, content_type: Optional[str] = None) -> str:
        try:
            from qiniu import put_file
        except ImportError:
            raise ImportError("`qiniu` not installed. Run: pip install qiniu")
        key = self._full_key(object_key)
        ct = content_type or self._infer_content_type(local_path)
        log_debug(f"Qiniu upload: {local_path} -> {self.bucket_name}/{key} (content-type: {ct})")
        auth = self._get_auth()
        token = auth.upload_token(self.bucket_name, key)
        ret, info = put_file(token, key, local_path, mime_type=ct)
        if info.status_code != 200:
            raise RuntimeError(f"Qiniu upload failed: {info}")
        return self._base_url(key)

    def sign_url(self, base_url: str, expires: int = 3600) -> str:
        log_debug(f"Qiniu sign_url: {base_url}  expires={expires}s")
        auth = self._get_auth()
        deadline = int(time.time()) + expires
        return auth.private_download_url(base_url, expires=deadline)
