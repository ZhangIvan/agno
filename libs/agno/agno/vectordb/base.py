from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from agno.knowledge.document import Document
from agno.knowledge.storage import PageImageStorage
from agno.utils.log import log_warning
from agno.utils.string import generate_id


class VectorDb(ABC):
    """Base class for Vector Databases"""

    def __init__(
        self,
        *,
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        similarity_threshold: Optional[float] = None,
        page_image_storage: Optional[PageImageStorage] = None,
        upload_concurrency: int = 10,
        url_signature_expires: int = 7200,
        **kwargs
    ):
        """Initialize base VectorDb.

        Args:
            id: Optional custom ID. If not provided, an id will be generated.
            name: Optional name for the vector database.
            description: Optional description for the vector database.
            similarity_threshold: Minimum similarity (0.0-1.0) to filter results.
        """
        if similarity_threshold is not None and not (0.0 <= similarity_threshold <= 1.0):
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")

        if name is None:
            name = self.__class__.__name__

        self.name = name
        self.description = description
        self.similarity_threshold = similarity_threshold
        # Last resort fallback to generate id from name if ID not specified
        self.id = id if id else generate_id(name)
        # Optional OSS/cloud storage backend for page images.
        # When set, page PNGs are uploaded at insert time and signed URLs are returned
        # at retrieval time instead of local file paths.
        self.page_image_storage: Optional[PageImageStorage] = page_image_storage  # PageImageStorage instance
        # --- Upload settings ---
        # Maximum number of concurrent image uploads (async path only).
        self.upload_concurrency: int = upload_concurrency
        # --- URL signature settings ---
        # Expiration time in seconds for signed URLs (default 7200 = 2 hours).
        # Only applies when page_image_storage is configured for private buckets.
        self.url_signature_expires: int = url_signature_expires

    @abstractmethod
    def create(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def async_create(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def name_exists(self, name: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def async_name_exists(self, name: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def id_exists(self, id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def content_hash_exists(self, content_hash: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def insert(self, content_hash: str, documents: List[Document], filters: Optional[Dict[str, Any]] = None) -> None:
        raise NotImplementedError

    @abstractmethod
    async def async_insert(
        self, content_hash: str, documents: List[Document], filters: Optional[Dict[str, Any]] = None
    ) -> None:
        raise NotImplementedError

    def upsert_available(self) -> bool:
        return False

    @abstractmethod
    def upsert(self, content_hash: str, documents: List[Document], filters: Optional[Dict[str, Any]] = None) -> None:
        raise NotImplementedError

    @abstractmethod
    async def async_upsert(
        self, content_hash: str, documents: List[Document], filters: Optional[Dict[str, Any]] = None
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, limit: int = 5, filters: Optional[Any] = None) -> List[Document]:
        raise NotImplementedError

    @abstractmethod
    async def async_search(self, query: str, limit: int = 5, filters: Optional[Any] = None) -> List[Document]:
        raise NotImplementedError

    @abstractmethod
    def drop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def async_drop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def async_exists(self) -> bool:
        raise NotImplementedError

    def optimize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete_by_id(self, id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete_by_name(self, name: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete_by_metadata(self, metadata: Dict[str, Any]) -> bool:
        raise NotImplementedError

    def update_metadata(self, content_id: str, metadata: Dict[str, Any]) -> None:
        """
        Update the metadata for documents with the given content_id.

        Default implementation logs a warning. Subclasses should override this method
        to provide their specific implementation.

        Args:
            content_id (str): The content ID to update
            metadata (Dict[str, Any]): The metadata to update
        """
        log_warning(
            f"{self.__class__.__name__}.update_metadata() is not implemented. "
            f"Metadata update for content_id '{content_id}' was skipped."
        )

    @abstractmethod
    def delete_by_content_id(self, content_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_supported_search_types(self) -> List[str]:
        raise NotImplementedError
