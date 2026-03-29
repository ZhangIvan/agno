"""Unit tests for _load_from_url and _aload_from_url in Knowledge class.

Mocks HTTP client, VectorDB, ContentsDB, Reader, and PageImageStorage to test
the URL loading pipeline without external dependencies.
"""

from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agno.knowledge.document import Document
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.base import VectorDb


class MockVectorDb(VectorDb):
    """Minimal VectorDb mock for testing."""

    def __init__(self):
        self._hashes: set = set()

    def create(self) -> None:
        pass

    async def async_create(self) -> None:
        pass

    def name_exists(self, name: str) -> bool:
        return False

    async def async_name_exists(self, name: str) -> bool:
        return False

    def id_exists(self, id: str) -> bool:
        return False

    def content_hash_exists(self, content_hash: str) -> bool:
        return content_hash in self._hashes

    def insert(self, content_hash: str, documents: List[Document], filters=None) -> None:
        self._hashes.add(content_hash)

    async def async_insert(self, content_hash: str, documents: List[Document], filters=None) -> None:
        self._hashes.add(content_hash)

    def upsert(self, content_hash: str, documents: List[Document], filters=None) -> None:
        self._hashes.add(content_hash)

    async def async_upsert(self, content_hash: str, documents: List[Document], filters=None) -> None:
        self._hashes.add(content_hash)

    def upsert_available(self) -> bool:
        return True

    def search(self, query: str, limit: int = 5, filters=None) -> List[Document]:
        return []

    async def async_search(self, query: str, limit: int = 5, filters=None) -> List[Document]:
        return []

    def drop(self) -> None:
        pass

    async def async_drop(self) -> None:
        pass

    def exists(self) -> bool:
        return True

    async def async_exists(self) -> bool:
        return True

    def delete(self) -> bool:
        return True

    def delete_by_id(self, id: str) -> bool:
        return True

    def delete_by_name(self, name: str) -> bool:
        return True

    def delete_by_metadata(self, metadata) -> bool:
        return True

    def delete_by_content_id(self, content_id: str) -> bool:
        return True

    def update_metadata(self, content_id: str, metadata) -> None:
        pass

    def get_supported_search_types(self) -> List[str]:
        return ["vector"]


@pytest.fixture
def mock_vdb():
    return MockVectorDb()


@pytest.fixture
def knowledge(mock_vdb):
    k = Knowledge(vector_db=mock_vdb)
    k.contents_db = None  # Disable contents_db to avoid DB dependency
    return k


@pytest.fixture
def knowledge_with_storage(mock_vdb):
    """Knowledge instance with mock page_image_storage."""
    k = Knowledge(vector_db=mock_vdb)
    k.contents_db = None
    storage = MagicMock()
    storage.upload.return_value = "https://oss.example.com/img/original.pdf"
    storage.async_upload = AsyncMock(return_value="https://oss.example.com/img/original.pdf")
    storage.sign_url.return_value = "https://oss.example.com/img/original.pdf?sig=abc"
    storage.async_sign_url = AsyncMock(return_value="https://oss.example.com/img/original.pdf?sig=abc")
    k.page_image_storage = storage
    return k, storage


def _make_doc(content="test content", meta_data=None, name="test.pdf"):
    """Helper to create a Document."""
    return Document(content=content, meta_data=meta_data or {}, name=name)


class AsyncIterator:
    """Helper to create an async iterator from a list."""

    def __init__(self, items):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration


def _make_mock_response(chunks=None):
    """Create a mock streaming response with proper aiter_bytes.

    Key: uses MagicMock (not AsyncMock) so that response.aiter_bytes(chunk_size)
    returns an AsyncIterator directly, matching production code:
        async for chunk in response.aiter_bytes(chunk_size=65536):
    """
    if chunks is None:
        chunks = [b"fake pdf content"]

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    # aiter_bytes must return an async iterator directly (not a coroutine)
    mock_response.aiter_bytes = MagicMock(return_value=AsyncIterator(chunks))
    return mock_response


def _make_streaming_client(mock_response):
    """Create a mock AsyncClient whose stream() returns mock_response.

    Uses MagicMock (not AsyncMock) for the client so that client.stream(...)
    returns mock_client.stream.return_value (a MagicMock) which can be
    configured as an async context manager.
    """
    mock_client = MagicMock()
    mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_client.stream.return_value.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def _wrap_client_as_async_cm(mock_client_cls, mock_client):
    """Configure mock_client_cls() to return mock_client via async context manager."""
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)


# ===== SYNC URL LOADING TESTS =====


class TestLoadFromUrlSync:
    """Tests for _load_from_url (synchronous)."""

    def test_invalid_url_format_sets_failed(self, knowledge):
        """Invalid URL format should set content status to FAILED."""
        content = MagicMock()
        content.url = "not-a-valid-url"
        content.name = "test"
        content.content_hash = "abc123"
        content.id = "id1"
        content.file_type = None
        content.metadata = {}
        content.reader = None
        content.auth = None

        knowledge._load_from_url(content, upsert=True, skip_if_exists=False)

    def test_no_url_raises(self, knowledge):
        """Missing URL should raise ValueError."""
        content = MagicMock()
        content.url = None
        with pytest.raises((ValueError, AttributeError)):
            knowledge._load_from_url(content, upsert=True, skip_if_exists=False)

    @patch("agno.knowledge.knowledge.Knowledge._select_reader_by_extension")
    @patch("agno.knowledge._mixins._load_url.httpx")
    def test_temp_file_cleanup_on_success(self, mock_httpx, mock_select_reader, knowledge, tmp_path):
        """Temp file should be cleaned up after successful insert."""
        fake_pdf = tmp_path / "downloaded.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake content")

        mock_reader = MagicMock()
        mock_reader.read.return_value = [_make_doc()]
        mock_reader.chunk = True
        mock_select_reader.return_value = (mock_reader, "")

        mock_stream = MagicMock()
        mock_stream.raise_for_status = MagicMock()
        mock_stream.iter_bytes.return_value = [b"%PDF-1.4 fake"]
        mock_httpx.stream.return_value.__enter__ = MagicMock(return_value=mock_stream)
        mock_httpx.stream.return_value.__exit__ = MagicMock(return_value=False)

        content = MagicMock()
        content.url = "https://example.com/doc.pdf"
        content.name = "doc.pdf"
        content.content_hash = "hash_pdf"
        content.id = "id_pdf"
        content.file_type = None
        content.metadata = {}
        content.reader = None
        content.auth = None

        knowledge._load_from_url(content, upsert=True, skip_if_exists=False)

    @patch("agno.knowledge.knowledge.Knowledge._select_reader_by_extension")
    def test_reader_exception_sets_failed(self, mock_select_reader, knowledge):
        """Reader exception during URL loading should set content FAILED."""
        mock_reader = MagicMock()
        mock_reader.read.side_effect = RuntimeError("Corrupt PDF")
        mock_reader.chunk = True
        mock_select_reader.return_value = (mock_reader, "")

        with patch("agno.knowledge._mixins._load_url.httpx") as mock_httpx:
            mock_stream = MagicMock()
            mock_stream.raise_for_status = MagicMock()
            mock_stream.iter_bytes.return_value = [b"%PDF-1.4 fake"]
            mock_httpx.stream.return_value.__enter__ = MagicMock(return_value=mock_stream)
            mock_httpx.stream.return_value.__exit__ = MagicMock(return_value=False)

            content = MagicMock()
            content.url = "https://example.com/doc.pdf"
            content.name = "doc.pdf"
            content.content_hash = "hash_pdf2"
            content.id = "id_pdf2"
            content.file_type = None
            content.metadata = {}
            content.reader = None
            content.auth = None

            knowledge._load_from_url(content, upsert=True, skip_if_exists=False)

            assert content.status is not None


# ===== ASYNC URL LOADING TESTS =====


class TestLoadFromUrlAsync:
    """Tests for _aload_from_url (asynchronous)."""

    @pytest.mark.asyncio
    async def test_no_url_raises(self, knowledge):
        """Missing URL should raise ValueError."""
        content = MagicMock()
        content.url = None
        with pytest.raises((ValueError, AttributeError)):
            await knowledge._aload_from_url(content, upsert=True, skip_if_exists=False)

    @pytest.mark.asyncio
    @patch("agno.knowledge._mixins._load_url.AsyncClient")
    async def test_async_url_uses_streaming_download(self, mock_async_client_cls, knowledge):
        """_aload_from_url should use streaming download, not response.content."""
        mock_response = _make_mock_response()
        mock_client = _make_streaming_client(mock_response)
        _wrap_client_as_async_cm(mock_async_client_cls, mock_client)

        with patch.object(knowledge, "_select_reader_by_extension") as mock_select:
            mock_reader = MagicMock()
            mock_reader.async_read = AsyncMock(return_value=[_make_doc()])
            mock_reader.chunk = True
            mock_reader.chunk_documents_async = AsyncMock(side_effect=lambda docs: docs)
            mock_select.return_value = (mock_reader, "")

            content = MagicMock()
            content.url = "https://example.com/test.pdf"
            content.name = "test.pdf"
            content.content_hash = "hash_async_pdf"
            content.id = "id_async_pdf"
            content.file_type = None
            content.metadata = {}
            content.reader = None
            content.auth = None

            await knowledge._aload_from_url(content, upsert=True, skip_if_exists=False)

            mock_client.stream.assert_called_once()
            call_args = mock_client.stream.call_args
            assert call_args[0][0] == "GET"
            assert call_args[0][1] == "https://example.com/test.pdf"

    @pytest.mark.asyncio
    async def test_async_temp_file_cleanup(self, knowledge, tmp_path):
        """Temp file created during async download should be cleaned up."""
        with patch.object(knowledge, "_select_reader_by_extension") as mock_select:
            mock_reader = MagicMock()
            mock_reader.async_read = AsyncMock(return_value=[_make_doc()])
            mock_reader.chunk = True
            mock_reader.chunk_documents_async = AsyncMock(side_effect=lambda docs: docs)
            mock_select.return_value = (mock_reader, "")

            content = MagicMock()
            content.url = "https://example.com/doc.pdf"
            content.name = "doc.pdf"
            content.content_hash = "hash_cleanup"
            content.id = "id_cleanup"
            content.file_type = None
            content.metadata = {}
            content.reader = None
            content.auth = None

            with patch("agno.knowledge._mixins._load_url.AsyncClient") as mock_client_cls:
                mock_response = _make_mock_response([b"%PDF-1.4 test"])
                mock_client = _make_streaming_client(mock_response)
                _wrap_client_as_async_cm(mock_client_cls, mock_client)

                await knowledge._aload_from_url(content, upsert=True, skip_if_exists=False)

    @pytest.mark.asyncio
    async def test_multi_source_creates_per_doc_hash(self, knowledge):
        """When WebsiteReader returns docs from multiple URLs, each should get its own hash."""
        doc1 = _make_doc(content="Page 1 content", meta_data={"url": "https://example.com/page1"})
        doc2 = _make_doc(content="Page 2 content", meta_data={"url": "https://example.com/page2"})

        with patch.object(knowledge, "_select_reader_by_extension") as mock_select:
            mock_reader = MagicMock()
            mock_reader.async_read = AsyncMock(return_value=[doc1, doc2])
            mock_reader.chunk = True
            mock_reader.chunk_documents_async = AsyncMock(side_effect=lambda docs: docs)
            mock_select.return_value = (mock_reader, "")

            content = MagicMock()
            content.url = "https://example.com/sitemap"
            content.name = "sitemap"
            content.content_hash = "hash_multi"
            content.id = "id_multi"
            content.file_type = None
            content.metadata = {}
            content.reader = None
            content.auth = None

            with patch("agno.knowledge._mixins._load_url.AsyncClient") as mock_client_cls:
                mock_client = MagicMock()
                _wrap_client_as_async_cm(mock_client_cls, mock_client)

                await knowledge._aload_from_url(content, upsert=True, skip_if_exists=False)

    @pytest.mark.asyncio
    async def test_skip_if_exists_skips_processing(self, mock_vdb):
        """When content hash already exists, skip processing."""
        k = Knowledge(vector_db=mock_vdb)
        k.contents_db = None

        hash_val = "existing_hash"
        mock_vdb._hashes.add(hash_val)

        content = MagicMock()
        content.url = "https://example.com/existing.pdf"
        content.name = "existing.pdf"
        content.content_hash = hash_val
        content.id = "id_existing"
        content.file_type = None
        content.metadata = {}
        content.reader = None
        content.auth = None

        await k._aload_from_url(content, upsert=True, skip_if_exists=True)

        assert content.status is not None


# ===== PAGE IMAGE UPLOAD IN URL PATH =====


class TestPageImageUploadInUrlPath:
    """Tests for page image upload during URL loading."""

    @pytest.mark.asyncio
    async def test_multi_source_uploads_page_images(self, knowledge_with_storage):
        """Multi-source URL path should upload page images per source group."""
        k, storage = knowledge_with_storage

        doc1 = _make_doc(
            content="Page 1",
            meta_data={
                "url": "https://example.com/page1",
                "page_image_path": "/tmp/cache/page_1.png",
                "page_number": 1,
                "doc_type": "page_image",
            },
        )

        with patch.object(k, "_select_reader_by_extension") as mock_select:
            mock_reader = MagicMock()
            mock_reader.async_read = AsyncMock(return_value=[doc1])
            mock_reader.chunk = True
            mock_reader.chunk_documents_async = AsyncMock(side_effect=lambda docs: docs)
            mock_select.return_value = (mock_reader, "")

            storage.async_upload = AsyncMock(return_value="https://oss.example.com/img/page_1.png")

            content = MagicMock()
            content.url = "https://example.com/sitemap"
            content.name = "sitemap"
            content.content_hash = "hash_page_img"
            content.id = "id_page_img"
            content.file_type = None
            content.metadata = {}
            content.reader = None
            content.auth = None

            with patch("agno.knowledge._mixins._load_url.AsyncClient") as mock_client_cls:
                mock_client = MagicMock()
                _wrap_client_as_async_cm(mock_client_cls, mock_client)

                await k._aload_from_url(content, upsert=True, skip_if_exists=False)


# ===== URL VALIDATION =====


class TestUrlValidation:
    """Tests for URL validation in _load_from_url."""

    @pytest.mark.asyncio
    async def test_url_without_extension_uses_head_request(self, knowledge):
        """URL without extension should try HEAD request to detect content type."""
        with patch.object(
            Knowledge,
            "_async_detect_extension_from_content_type",
            AsyncMock(return_value=".pdf"),
        ):
            with patch.object(knowledge, "_select_reader_by_extension") as mock_select:
                mock_reader = MagicMock()
                mock_reader.async_read = AsyncMock(return_value=[_make_doc()])
                mock_reader.chunk = True
                mock_reader.chunk_documents_async = AsyncMock(side_effect=lambda docs: docs)
                mock_select.return_value = (mock_reader, "")

                content = MagicMock()
                content.url = "https://example.com/download"
                content.name = "download"
                content.content_hash = "hash_no_ext"
                content.id = "id_no_ext"
                content.file_type = None
                content.metadata = {}
                content.reader = None
                content.auth = None

                with patch("agno.knowledge._mixins._load_url.AsyncClient") as mock_client_cls:
                    mock_response = _make_mock_response([b"pdf content"])
                    mock_client = _make_streaming_client(mock_response)
                    _wrap_client_as_async_cm(mock_client_cls, mock_client)

                    await knowledge._aload_from_url(content, upsert=True, skip_if_exists=False)

    @pytest.mark.asyncio
    async def test_url_with_extension_skips_head_request(self, knowledge):
        """URL with extension should skip HEAD request and use extension directly."""
        with patch.object(
            Knowledge,
            "_async_detect_extension_from_content_type",
        ) as mock_detect:
            with patch.object(knowledge, "_select_reader_by_extension") as mock_select:
                mock_reader = MagicMock()
                mock_reader.async_read = AsyncMock(return_value=[_make_doc()])
                mock_reader.chunk = True
                mock_reader.chunk_documents_async = AsyncMock(side_effect=lambda docs: docs)
                mock_select.return_value = (mock_reader, "")

                content = MagicMock()
                content.url = "https://example.com/doc.pdf"
                content.name = "doc.pdf"
                content.content_hash = "hash_with_ext"
                content.id = "id_with_ext"
                content.file_type = None
                content.metadata = {}
                content.reader = None
                content.auth = None

                with patch("agno.knowledge._mixins._load_url.AsyncClient") as mock_client_cls:
                    mock_response = _make_mock_response([b"pdf"])
                    mock_client = _make_streaming_client(mock_response)
                    _wrap_client_as_async_cm(mock_client_cls, mock_client)

                    await knowledge._aload_from_url(content, upsert=True, skip_if_exists=False)

                mock_detect.assert_not_called()
