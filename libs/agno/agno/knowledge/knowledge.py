from dataclasses import dataclass
from typing import Dict, List, Optional, Union, cast

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agno.vectordb.base import VectorDb

from agno.db.base import AsyncBaseDb, BaseDb
from agno.knowledge._mixins import (
    _KnowledgeContentLoaderMixin,
    _KnowledgeContentManagementMixin,
    _KnowledgeDataMixin,
    _KnowledgeDatabaseMixin,
    _KnowledgeDeprecatedMixin,
    _KnowledgeFilterMixin,
    _KnowledgeInsertMixin,
    _KnowledgeLightRAGMixin,
    _KnowledgeLoadingMixin,
    _KnowledgePageImageMixin,
    _KnowledgePathLoaderMixin,
    _KnowledgeReaderMixin,
    _KnowledgeRetrievalMixin,
    _KnowledgeSearchMixin,
    _KnowledgeToolMixin,
    _KnowledgeTopicLoaderMixin,
    _KnowledgeUrlLoaderMixin,
)
from agno.knowledge.reader import Reader
from agno.knowledge.remote_content.base import BaseStorageConfig
from agno.knowledge.remote_knowledge import RemoteKnowledge
from agno.knowledge.types import PageImageStorage


@dataclass
class Knowledge(
    _KnowledgeDeprecatedMixin,
    _KnowledgeToolMixin,
    _KnowledgePageImageMixin,
    _KnowledgeRetrievalMixin,
    _KnowledgeLightRAGMixin,
    _KnowledgeDatabaseMixin,
    _KnowledgeDataMixin,
    _KnowledgeUrlLoaderMixin,
    _KnowledgeContentLoaderMixin,
    _KnowledgeTopicLoaderMixin,
    _KnowledgePathLoaderMixin,
    _KnowledgeLoadingMixin,
    _KnowledgeReaderMixin,
    _KnowledgeFilterMixin,
    _KnowledgeContentManagementMixin,
    _KnowledgeSearchMixin,
    _KnowledgeInsertMixin,
    RemoteKnowledge,
):
    """Knowledge class"""

    name: Optional[str] = None
    description: Optional[str] = None
    vector_db: Optional["VectorDb"] = None
    contents_db: Optional[Union[BaseDb, AsyncBaseDb]] = None
    max_results: int = 10
    readers: Optional[Dict[str, Reader]] = None
    content_sources: Optional[List[BaseStorageConfig]] = None
    # When True, adds linked_to metadata during insert and filters by it during search.
    # This enables isolation when multiple Knowledge instances share the same vector database.
    # Requires re-indexing existing data to add linked_to metadata.
    # Default is False for backwards compatibility with existing data.
    isolate_vector_search: bool = False

    # --- Page image retrieval settings ---
    # When True, retrieved text chunks are replaced by their corresponding page images
    # when sent to the LLM. Requires documents to have page_image_path in metadata.
    use_page_images: bool = False
    # Maximum number of page images to include in a single retrieval response.
    max_retrieval_images: int = 3
    # Sliding window around each matched page (±N pages). 1 means prev+current+next.
    image_window_size: int = 0
    # Optional OSS/cloud storage backend for page images.
    # When set, page PNGs are uploaded at insert time and signed URLs are returned
    # at retrieval time instead of local file paths.
    page_image_storage: Optional[PageImageStorage] = None  # PageImageStorage instance
    # --- Upload settings ---
    # Maximum number of concurrent image uploads (async path only).
    upload_concurrency: int = 10
    # Maximum retry attempts per upload on transient failures.
    upload_max_retries: int = 3
    # Base delay in seconds for exponential backoff between retries.
    upload_retry_base_delay: float = 0.5
    # --- Image URL verification ---
    # When True, perform a lightweight HEAD request to verify image URLs are
    # accessible before passing them to the LLM.  Default is False since
    # invalid URLs are rare and the check adds latency.
    verify_image_urls: bool = False
    # Timeout in seconds for the HEAD request when verify_image_urls is True.
    verify_image_url_timeout: float = 1.0
    # --- URL signature settings ---
    # Expiration time in seconds for signed URLs (default 7200 = 2 hours).
    # Only applies when page_image_storage is configured for private buckets.
    url_signature_expires: int = 7200

    def __post_init__(self):
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)
        if self.vector_db and not self.vector_db.exists():
            self.vector_db.create()

        self.construct_readers()
