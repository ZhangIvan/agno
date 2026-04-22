from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class UploadCredentialsRequest(BaseModel):
    """Request body for getting upload credentials."""

    storage_id: Optional[str] = Field(None, description="Storage instance identifier (e.g., name or index)")
    prefix: Optional[str] = Field(None, description="Key prefix for uploads (e.g., 'uploads/')")
    file_extension: Optional[str] = Field(None, description="Expected file extension (e.g., '.png')")
    content_type: Optional[str] = Field(None, description="Allowed content type (e.g., 'image/png')")
    expires: int = Field(3600, description="Credential validity in seconds", ge=60, le=43200)


class UploadCredentialsResponse(BaseModel):
    """Response with upload credentials for frontend direct upload."""

    provider: str = Field(..., description="Storage provider name")
    upload_url: Optional[str] = Field(None, description="Presigned URL for direct upload")
    object_key: Optional[str] = Field(None, description="Object key for the uploaded file")
    object_url: Optional[str] = Field(None, description="Final URL after upload")
    headers: Optional[Dict[str, str]] = Field(None, description="Required headers for the upload request")
    expires_at: Optional[str] = Field(None, description="ISO 8601 expiration timestamp")
    token: Optional[str] = Field(None, description="Upload token (for providers like Qiniu)")


class StorageInfo(BaseModel):
    """Information about a configured storage backend."""

    id: Optional[str] = None
    provider: str
    bucket: Optional[str] = None
    prefix: Optional[str] = None


class StorageListResponse(BaseModel):
    """List of available storage backends."""

    storages: List[StorageInfo]
