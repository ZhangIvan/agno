"""Storage router — endpoints for frontend direct file upload via presigned credentials."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from agno.knowledge.storage.base import PageImageStorage
from agno.os.auth import get_authentication_dependency
from agno.os.routers.storage.schemas import (
    StorageInfo,
    StorageListResponse,
    UploadCredentialsRequest,
    UploadCredentialsResponse,
)
from agno.os.settings import AgnoAPISettings
from agno.utils.log import logger


def get_storage_router(
    storages: Optional[List[PageImageStorage]] = None,
    storage_ids: Optional[List[str]] = None,
    settings: AgnoAPISettings = AgnoAPISettings(),
) -> APIRouter:
    """Create the storage router for frontend direct upload.

    Args:
        storages: List of configured PageImageStorage instances.
        storage_ids: Optional list of identifiers for each storage instance.
        settings: API settings for authentication.
    """
    router = APIRouter(
        dependencies=[Depends(get_authentication_dependency(settings))],
        tags=["Storage"],
        responses={
            400: {"description": "Bad Request"},
            401: {"description": "Unauthorized"},
            404: {"description": "Not Found"},
            500: {"description": "Internal Server Error"},
        },
    )

    _storages = storages or []
    _storage_ids = storage_ids or [f"storage-{i}" for i in range(len(_storages))]

    @router.get(
        "/storages",
        response_model=StorageListResponse,
        operation_id="list_storages",
        summary="List available storage backends",
    )
    async def list_storages() -> StorageListResponse:
        """List all configured storage backends."""
        storage_list = []
        for idx, storage in enumerate(_storages):
            storage_id = _storage_ids[idx] if idx < len(_storage_ids) else f"storage-{idx}"
            provider = type(storage).__name__
            bucket = getattr(storage, "bucket_name", None) or getattr(storage, "domain", None)
            prefix = getattr(storage, "key_prefix", None)
            storage_list.append(StorageInfo(id=storage_id, provider=provider, bucket=bucket, prefix=prefix))
        return StorageListResponse(storages=storage_list)

    @router.post(
        "/storage/upload-credentials",
        response_model=UploadCredentialsResponse,
        operation_id="get_upload_credentials",
        summary="Get upload credentials for frontend direct upload",
    )
    async def get_upload_credentials(request: UploadCredentialsRequest) -> UploadCredentialsResponse:
        """Get temporary upload credentials (presigned URL or token) for frontend direct file upload.

        The frontend can use the returned credentials to upload a file directly to the
        object storage without going through the backend server.
        """
        if not _storages:
            raise HTTPException(status_code=503, detail="No storage backends configured")

        # Find the matching storage backend
        storage: Optional[PageImageStorage] = None
        if request.storage_id:
            for idx, sid in enumerate(_storage_ids):
                if sid == request.storage_id and idx < len(_storages):
                    storage = _storages[idx]
                    break
            if storage is None:
                raise HTTPException(status_code=404, detail=f"Storage '{request.storage_id}' not found")
        else:
            # Default to the first storage
            storage = _storages[0]

        # Build prefix from request
        prefix = request.prefix or "uploads"

        # Get upload credentials from the storage backend
        try:
            creds = storage.get_upload_credentials(
                prefix=prefix,
                expires=request.expires,
                content_type=request.content_type,
                file_extension=request.file_extension or "",
            )
        except NotImplementedError as e:
            raise HTTPException(status_code=501, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to get upload credentials: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get upload credentials: {e}")

        return UploadCredentialsResponse(
            provider=creds.get("provider", type(storage).__name__),
            upload_url=creds.get("upload_url"),
            object_key=creds.get("object_key"),
            object_url=creds.get("object_url"),
            headers=creds.get("headers"),
            expires_at=creds.get("expires_at"),
            token=creds.get("token"),
        )

    return router
