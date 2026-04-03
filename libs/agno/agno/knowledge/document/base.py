from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agno.knowledge.embedder import Embedder


@dataclass
class Document:
    """Dataclass for managing a document"""

    content: str
    id: Optional[str] = None
    name: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)
    embedder: Optional["Embedder"] = None
    embedding: Optional[List[float]] = None
    usage: Optional[Dict[str, Any]] = None
    reranking_score: Optional[float] = None
    content_id: Optional[str] = None
    content_origin: Optional[str] = None
    size: Optional[int] = None
    # Transient field: local image path used only during embedding, never stored.
    # Set by _upload_page_images() so the local file is available for embedding
    # inside vector_db.insert() even though page_image_path has been removed from
    # meta_data (preventing it from being persisted to the vector store).
    local_embed_path: Optional[str] = field(default=None, repr=False, compare=False)

    def embed(self, embedder: Optional[Embedder] = None) -> None:
        """Embed the document using the provided embedder"""

        _embedder = embedder or self.embedder
        if _embedder is None:
            raise ValueError("No embedder provided")

        # Image documents: embed using image embedding when available
        if self.meta_data.get("doc_type") == "page_image":
            # Priority: transient local path (set during insert, no signing needed)
            # → meta page_image_path (backward compat for callers not using storage)
            # → OSS URL fallback (post-cleanup or re-embed scenarios)
            image_ref = (
                self.meta_data.get("page_image_url_sign")
                or self.local_embed_path
                or self.meta_data.get("page_image_url")
                or self.meta_data.get("page_image_path")
            )
            if image_ref:
                img_embedding, img_usage = _embedder.get_image_embedding_and_usage(image_ref)
                if img_embedding is not None:
                    self.embedding = img_embedding
                    self.usage = img_usage
                    return

        self.embedding, self.usage = _embedder.get_embedding_and_usage(self.content)

    async def async_embed(self, embedder: Optional[Embedder] = None) -> None:
        """Embed the document using the provided embedder"""
        _embedder = embedder or self.embedder
        if _embedder is None:
            raise ValueError("No embedder provided")

        # Image documents: embed using image embedding when available
        if self.meta_data.get("doc_type") == "page_image":
            # Priority: transient local path → meta page_image_path → OSS URL

            image_ref = (
                self.meta_data.get("page_image_url_sign")
                or self.local_embed_path
                or self.meta_data.get("page_image_url")
                or self.meta_data.get("page_image_path")
            )
            if image_ref:
                img_embedding, img_usage = await _embedder.async_get_image_embedding_and_usage(image_ref)
                if img_embedding is not None:
                    self.embedding = img_embedding
                    self.usage = img_usage
                    return

        self.embedding, self.usage = await _embedder.async_get_embedding_and_usage(self.content)

    def to_dict(self) -> Dict[str, Any]:
        """Returns a dictionary representation of the document"""
        fields = {"name", "meta_data", "content"}
        return {
            field: getattr(self, field)
            for field in fields
            if getattr(self, field) is not None or field == "content"  # content is always included
        }

    @classmethod
    def from_dict(cls, document: Dict[str, Any]) -> "Document":
        """Returns a Document object from a dictionary representation"""
        return cls(**document)

    @classmethod
    def from_json(cls, document: str) -> "Document":
        """Returns a Document object from a json string representation"""
        import json

        return cls(**json.loads(document))
