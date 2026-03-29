"""Content loading dispatch and helper methods for the Knowledge class.

Dispatchers route content to the appropriate loader (path, url, content, topic).
Helper methods handle skip logic, extension detection, reader selection, and
document preparation.
"""

import asyncio
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast

from httpx import AsyncClient

from agno.knowledge.content import Content
from agno.knowledge.document import Document
from agno.knowledge.reader import Reader
from agno.knowledge.types import SUPPORTED_IMAGE_EXTENSIONS
from agno.knowledge.utils import MIME_TO_EXTENSION
from agno.utils.log import log_debug


class _KnowledgeLoadingMixin:
    """Content loading dispatch, skip helpers, extension detection, reader selection, document preparation."""

    # ----- Dispatchers -----

    def _load_content(
        self,
        content: Content,
        upsert: bool,
        skip_if_exists: bool,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
    ) -> None:
        """Synchronously load content."""
        if content.path:
            self._load_from_path(content, upsert, skip_if_exists, include, exclude)

        if content.url:
            self._load_from_url(content, upsert, skip_if_exists)

        if content.file_data:
            self._load_from_content(content, upsert, skip_if_exists)

        if content.topics:
            self._load_from_topics(content, upsert, skip_if_exists)

        if content.remote_content:
            self._load_from_remote_content(content, upsert, skip_if_exists)

    async def _aload_content(
        self,
        content: Content,
        upsert: bool,
        skip_if_exists: bool,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
    ) -> None:
        if content.path:
            await self._aload_from_path(content, upsert, skip_if_exists, include, exclude)

        if content.url:
            await self._aload_from_url(content, upsert, skip_if_exists)

        if content.file_data:
            await self._aload_from_content(content, upsert, skip_if_exists)

        if content.topics:
            await self._aload_from_topics(content, upsert, skip_if_exists)

        if content.remote_content:
            await self._aload_from_remote_content(content, upsert, skip_if_exists)

    # ----- Skip helpers -----

    def _should_skip(self, content_hash: str, skip_if_exists: bool) -> bool:
        """
        Handle the skip_if_exists logic for content that already exists in the vector database.

        Args:
            content_hash: The content hash string to check for existence
            skip_if_exists: Whether to skip if content already exists

        Returns:
            bool: True if should skip processing, False if should continue
        """
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)
        if self.vector_db and self.vector_db.content_hash_exists(content_hash) and skip_if_exists:
            log_debug(f"Content already exists: {content_hash}, skipping...")
            return True

        return False

    async def _async_should_skip(self, content_hash: str, skip_if_exists: bool) -> bool:
        """Async version of :meth:`_should_skip`."""

        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)
        if (
            self.vector_db
            and await asyncio.to_thread(self.vector_db.content_hash_exists, content_hash)
            and skip_if_exists
        ):
            log_debug(f"Content already exists: {content_hash}, skipping...")
            return True

        return False

    # ----- Extension detection -----

    @staticmethod
    def _detect_extension_from_content_type(url: str) -> Optional[str]:
        """HEAD request to detect Content-Type, return inferred extension or None."""
        try:
            import httpx

            with httpx.Client(follow_redirects=True, timeout=10) as client:
                resp = client.head(url)
                content_type = resp.headers.get("content-type", "")
                mime = content_type.split(";")[0].strip().lower()
                return MIME_TO_EXTENSION.get(mime)
        except Exception:
            return None

    @staticmethod
    async def _async_detect_extension_from_content_type(url: str) -> Optional[str]:
        """Async HEAD request to detect Content-Type."""
        try:
            async with AsyncClient(follow_redirects=True, timeout=10) as client:
                resp = await client.head(url)
                content_type = resp.headers.get("content-type", "")
                mime = content_type.split(";")[0].strip().lower()
                return MIME_TO_EXTENSION.get(mime)
        except Exception:
            return None

    # ----- Reader selection -----

    def _select_reader_by_extension(
        self, file_extension: str, provided_reader: Optional[Reader] = None
    ) -> Tuple[Optional[Reader], str]:
        """
        Select a reader based on file extension.

        Args:
            file_extension: File extension (e.g., '.pdf', '.csv')
            provided_reader: Optional reader already provided

        Returns:
            Tuple of (reader, name) where name may be adjusted based on extension
        """
        if provided_reader:
            return provided_reader, ""

        file_extension = file_extension.lower()
        if file_extension == ".csv":
            return self.csv_reader, "data.csv"
        elif file_extension == ".pdf":
            return self.pdf_reader, ""
        elif file_extension == ".docx":
            return self.docx_reader, ""
        elif file_extension == ".pptx":
            return self.pptx_reader, ""
        elif file_extension == ".json":
            return self.json_reader, ""
        elif file_extension == ".markdown":
            return self.markdown_reader, ""
        elif file_extension in [".xlsx", ".xls"]:
            return self.excel_reader, ""
        elif file_extension in SUPPORTED_IMAGE_EXTENSIONS:
            return self.image_reader, ""
        else:
            return self.text_reader, ""

    def _select_reader_by_uri(self, uri: str, provided_reader: Optional[Reader] = None) -> Optional[Reader]:
        """
        Select a reader based on URI/file path extension.

        Args:
            uri: URI or file path
            provided_reader: Optional reader already provided

        Returns:
            Selected reader or None
        """
        if provided_reader:
            return provided_reader

        uri_lower = uri.lower()
        if uri_lower.endswith(".pdf"):
            return self.pdf_reader
        elif uri_lower.endswith(".csv"):
            return self.csv_reader
        elif uri_lower.endswith(".docx"):
            return self.docx_reader
        elif uri_lower.endswith(".pptx"):
            return self.pptx_reader
        elif uri_lower.endswith(".json"):
            return self.json_reader
        elif uri_lower.endswith(".markdown"):
            return self.markdown_reader
        elif uri_lower.endswith(".xlsx") or uri_lower.endswith(".xls"):
            return self.excel_reader
        elif any(uri_lower.endswith(ext) for ext in SUPPORTED_IMAGE_EXTENSIONS):
            return self.image_reader
        else:
            return self.text_reader

    # ----- Read helpers -----

    def _read(
        self,
        reader: Reader,
        source: Union[Path, str, BytesIO],
        name: Optional[str] = None,
        password: Optional[str] = None,
    ) -> List[Document]:
        """
        Read content using a reader with optional password handling.

        Args:
            reader: Reader to use
            source: Source to read from (Path, URL string, or BytesIO)
            name: Optional name for the document
            password: Optional password for protected files

        Returns:
            List of documents read
        """
        import inspect

        read_signature = inspect.signature(reader.read)
        if password is not None and "password" in read_signature.parameters:
            return reader.read(source, name=name, password=password)
        else:
            return reader.read(source, name=name)

    async def _aread(
        self,
        reader: Reader,
        source: Union[Path, str, BytesIO],
        name: Optional[str] = None,
        password: Optional[str] = None,
    ) -> List[Document]:
        """
        Read content using a reader's async_read method with optional password handling.

        Args:
            reader: Reader to use
            source: Source to read from (Path, URL string, or BytesIO)
            name: Optional name for the document
            password: Optional password for protected files

        Returns:
            List of documents read
        """
        import inspect

        read_signature = inspect.signature(reader.async_read)
        if password is not None and "password" in read_signature.parameters:
            return await reader.async_read(source, name=name, password=password)
        else:
            return await reader.async_read(source, name=name)

    # ----- Document preparation -----

    def _prepare_documents_for_insert(
        self,
        documents: List[Document],
        content_id: str,
        calculate_sizes: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """
        Prepare documents for insertion by assigning content_id and optionally calculating sizes and updating metadata.

        Args:
            documents: List of documents to prepare
            content_id: Content ID to assign to documents
            calculate_sizes: Whether to calculate document sizes
            metadata: Optional metadata to merge into document metadata

        Returns:
            List of prepared documents
        """
        for document in documents:
            document.content_id = content_id
            if calculate_sizes and document.content and not document.size:
                document.size = len(document.content.encode("utf-8"))
            if metadata:
                document.meta_data.update(metadata)
            document.meta_data["linked_to"] = self.name or ""
        return documents

    def _chunk_documents_sync(self, reader: Reader, documents: List[Document]) -> List[Document]:
        """
        Chunk documents synchronously.

        Args:
            reader: Reader with chunking strategy
            documents: Documents to chunk

        Returns:
            List of chunked documents
        """
        if not reader or reader.chunk:
            return documents

        chunked_documents = []
        for doc in documents:
            chunked_documents.extend(reader.chunk_document(doc))
        return chunked_documents
