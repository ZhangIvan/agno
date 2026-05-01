"""Tencent Cloud COS (Cloud Object Storage) backend for page images.

Requirements:
    pip install cos-python-sdk-v5
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from agno.knowledge.storage.base import PageImageStorage
from agno.knowledge.storage.exceptions import OSSDeleteError, OSSUploadError
from agno.utils.log import log_debug


@dataclass
class TencentCOSStorage(PageImageStorage):
    """Tencent Cloud COS storage backend.

    Example::

        storage = TencentCOSStorage(
            secret_id="...",
            secret_key="...",
            region="ap-shanghai",
            bucket_name="my-bucket-1250000000",
        )
    """

    secret_id: str = ""
    secret_key: str = ""
    region: str = ""
    bucket_name: str = ""
    # Optional custom domain for URL generation
    custom_domain: str = field(default="", repr=False)
    # Whether the bucket is private
    is_private: bool = field(default=True, repr=False)

    def _get_client(self):
        try:
            from qcloud_cos import CosConfig, CosS3Client
        except ImportError:
            raise ImportError("`cos-python-sdk-v5` not installed. Run: pip install cos-python-sdk-v5")
        config = CosConfig(Region=self.region, SecretId=self.secret_id, SecretKey=self.secret_key)
        return CosS3Client(config)

    def _base_url(self, key: str) -> str:
        if self.custom_domain:
            return f"{self._ensure_protocol(self.custom_domain)}/{key}"
        return f"https://{self.bucket_name}-cos.{self.region}.myqcloud.com/{key}"

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload(self, local_path: str, object_key: str, content_type: Optional[str] = None) -> str:
        ct = content_type or self._infer_content_type(local_path) or "application/octet-stream"
        log_debug(f"TencentCOS upload: {local_path} -> {self.bucket_name}/{object_key} (content-type: {ct})")

        def _do_upload():
            client = self._get_client()
            client.upload_file(
                Bucket=self.bucket_name,
                Key=object_key,
                LocalFilePath=local_path,
                EnableMD5=True,
                ContentType=ct,
            )
            return self._base_url(object_key)

        try:
            return self._with_retry(_do_upload, label=f"upload {self.bucket_name}/{object_key}")
        except Exception as e:
            raise OSSUploadError(f"TencentCOS upload failed: key={object_key}, file={local_path}, error={e}") from e

    def upload_bytes(self, data: bytes, object_key: str, content_type: Optional[str] = None) -> str:
        ct = content_type or self.guess_content_type(object_key) or "application/octet-stream"
        log_debug(f"TencentCOS upload_bytes: {len(data)} bytes -> {self.bucket_name}/{object_key}")

        def _do_upload():
            client = self._get_client()
            client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=data,
                ContentType=ct,
            )
            return self._base_url(object_key)

        try:
            return self._with_retry(_do_upload, label=f"upload_bytes {self.bucket_name}/{object_key}")
        except Exception as e:
            raise OSSUploadError(f"TencentCOS upload_bytes failed: key={object_key}, error={e}") from e

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

    def get_signed_url(self, key: str, expires: int = 3600) -> str:
        log_debug(f"TencentCOS get_signed_url: {key}  expires={expires}s")
        try:
            client = self._get_client()
            return client.get_presigned_download_url(
                Bucket=self.bucket_name,
                Key=key,
                Expired=expires,
            )
        except Exception as e:
            log_debug(f"TencentCOS sign_url failed, falling back to base URL: key={key}, error={e}")
            return self._base_url(key)

    def get_download_url(self, key: str, filename: str = "", expires: int = 3600) -> str:
        """Return a signed URL that triggers browser download via Content-Disposition."""
        if not filename:
            filename = key.rsplit("/", 1)[-1] if "/" in key else key
        disposition = f'attachment; filename="{filename}"'
        try:
            client = self._get_client()
            return client.get_presigned_download_url(
                Bucket=self.bucket_name,
                Key=key,
                Expired=expires,
                Params={"response-content-disposition": disposition},
            )
        except Exception as e:
            log_debug(f"TencentCOS download_url failed, falling back to signed URL: key={key}, error={e}")
            return self.get_signed_url(key, expires)

    # ------------------------------------------------------------------
    # Object management
    # ------------------------------------------------------------------

    def delete(self, object_key: str) -> bool:
        log_debug(f"TencentCOS delete: {self.bucket_name}/{object_key}")
        try:
            client = self._get_client()
            client.delete_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except Exception as e:
            raise OSSDeleteError(f"TencentCOS delete failed: key={object_key}, error={e}") from e

    def exists(self, object_key: str) -> bool:
        try:
            client = self._get_client()
            client.head_object(Bucket=self.bucket_name, Key=object_key)
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
                    return url[len(prefix) :].split("?")[0]

        # Standard format: https://{bucket}-cos.{region}.myqcloud.com/{key}
        base = f"{self.bucket_name}-cos.{self.region}.myqcloud.com"
        for proto in ["https://", "http://"]:
            prefix = f"{proto}{base}/"
            if url.startswith(prefix):
                return url[len(prefix) :].split("?")[0]

        return None

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

        client = self._get_client()
        cos_kwargs: Dict[str, Any] = {}
        if content_type:
            cos_kwargs["ContentType"] = content_type
        upload_url = client.get_presigned_url(
            Method="PUT",
            Bucket=self.bucket_name,
            Key=object_key,
            Expired=expires,
            **cos_kwargs,
        )

        return self._build_credential_response(
            provider="tencent_cos",
            upload_url=upload_url,
            object_key=object_key,
            content_type=content_type,
            expires_at=self._compute_expires_at(expires),
        )
