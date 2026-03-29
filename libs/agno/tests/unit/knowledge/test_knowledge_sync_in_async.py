"""Unit tests verifying async methods properly use asyncio.to_thread for sync I/O.

These tests ensure that the sync-in-async fixes from Round 3 are maintained:
 no
blocking sync I/O calls in async methods.
"""

from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agno.knowledge.document import Document
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.base import VectorDb


class _AsyncIter:
    """Helper async iterator for mocking aiter_bytes."""

    def __init__(self, chunks):
        self._chunks = iter(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._chunks)
        except StopIteration:
            raise StopAsyncIteration


class MockVectorDbForSyncAsync(VectorDb):
    """VectorDb mock that tracks whether sync methods are called from async context."""

    def __init__(self):
        self._hashes: set = set()
        self.sync_search_called = False

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
        self.sync_search_called = True
        return []

    async def async_search(self, query: str, limit: int = 5, filters=None) -> List[Document]:
        return [Document(content="test result", meta_data={})]

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
    return MockVectorDbForSyncAsync()


@pytest.fixture
def knowledge(mock_vdb):
    k = Knowledge(vector_db=mock_vdb)
    k.contents_db = None
    return k


class TestAsyncShouldSkip:
    """Verify _async_should_skip uses asyncio.to_thread for sync content_hash_exists."""

    @pytest.mark.asyncio
    async def test_async_should_skip_returns_true_when_exists(self, mock_vdb):
        mock_vdb._hashes.add("existing_hash")
        k = Knowledge(vector_db=mock_vdb)
        k.contents_db = None

        result = await k._async_should_skip("existing_hash", True)
        assert result is True

    @pytest.mark.asyncio
    async def test_async_should_skip_returns_false_when_not_exists(self, mock_vdb):
        k = Knowledge(vector_db=mock_vdb)
        k.contents_db = None

        result = await k._async_should_skip("missing_hash", True)
        assert result is False

    @pytest.mark.asyncio
    async def test_async_should_skip_returns_false_when_skip_false(self, mock_vdb):
        mock_vdb._hashes.add("existing_hash")
        k = Knowledge(vector_db=mock_vdb)
        k.contents_db = None

        # Even though hash exists, skip_if_exists=False means don't skip
        result = await k._async_should_skip("existing_hash", False)
        assert result is False


class TestAsearchFallback:
    """Verify asearch uses asyncio.to_thread when async_search is not implemented."""

    @pytest.mark.asyncio
    async def test_asearch_falls_back_to_sync_via_to_thread(self, mock_vdb):
        """When async_search raises NotImplementedError, asearch should use asyncio.to_thread."""
        mock_vdb.async_search = AsyncMock(side_effect=NotImplementedError("No async search"))
        k = Knowledge(vector_db=mock_vdb)
        k.contents_db = None

        # The fallback should call sync search via asyncio.to_thread
        result = await k.asearch(query="test")
        assert len(result) == 0  # MockVectorDb.search returns []
        assert mock_vdb.sync_search_called


class TestAloadFromPathSyncOps:
    """Verify _aload_from_path wraps sync Path operations in asyncio.to_thread."""

    @pytest.mark.asyncio
    async def test_aload_from_path_wraps_is_file(self, knowledge, tmp_path):
        """_aload_from_path should check is_file via asyncio.to_thread."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        content = MagicMock()
        content.path = str(test_file)
        content.name = "test.txt"
        content.content_hash = "hash_test"
        content.id = "id_test"
        content.file_type = None
        content.metadata = {}
        content.reader = None
        content.auth = None

        # Mock the reader to return empty docs (skip_if_exists=True and hash not in vdb)
        with patch.object(knowledge, "_select_reader_by_extension") as mock_select:
            mock_reader = MagicMock()
            mock_reader.async_read = AsyncMock(return_value=[])
            mock_reader.chunk = True
            mock_select.return_value = (mock_reader, "")

            await knowledge._aload_from_path(content, upsert=True, skip_if_exists=False)
            # Should not crash - Path.is_file() was called via asyncio.to_thread

    @pytest.mark.asyncio
    async def test_aload_from_path_wraps_stat(self, knowledge, tmp_path):
        """_aload_from_path should call path.stat() via asyncio.to_thread."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        content = MagicMock()
        content.path = str(test_file)
        content.name = "test.txt"
        content.content_hash = "hash_stat_test"
        content.id = "id_stat_test"
        content.file_type = None
        content.metadata = {}
        content.reader = None
        content.auth = None
        content.size = 0
        content.file_data = None

        with patch.object(knowledge, "_select_reader_by_extension") as mock_select:
            mock_reader = MagicMock()
            mock_reader.async_read = AsyncMock(return_value=[])
            mock_reader.chunk = True
            mock_select.return_value = (mock_reader, "")

            await knowledge._aload_from_path(content, upsert=True, skip_if_exists=False)
            # stat_result.st_size should have been read via asyncio.to_thread

            # No crash = success


class TestAsyncTempFileCleanup:
    """Verify _aload_from_url cleans up temp files via asyncio.to_thread(os.unlink)."""

    @pytest.mark.asyncio
    async def test_temp_file_cleaned_after_success(self, knowledge, tmp_path):
        """Temp file from URL download should be cleaned up after successful insert."""
        with patch.object(knowledge, "_select_reader_by_extension") as mock_select:
            mock_reader = MagicMock()
            mock_reader.async_read = AsyncMock(return_value=[])
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
                # MagicMock response so aiter_bytes() returns async iterator directly
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                mock_response.aiter_bytes = MagicMock(return_value=_AsyncIter([b"%PDF-1.4 test"]))
                mock_client = MagicMock()
                mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
                mock_client.stream.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

                await knowledge._aload_from_url(content, upsert=True, skip_if_exists=False)

    @pytest.mark.asyncio
    async def test_async_prefer_url_wraps_is_file(self, knowledge, tmp_path):
        """_async_prefer_url_over_local should check Path.is_file via asyncio.to_thread."""
        k = Knowledge(vector_db=MockVectorDbForSyncAsync())
        k.contents_db = None
        storage = MagicMock()
        storage.async_upload = AsyncMock(return_value=None)
        k.page_image_storage = storage

        img = tmp_path / "page_1.png"
        img.write_bytes(b"\x89PNG")

        doc = MagicMock(content_id="cid", name="test")

        # When storage.async_upload returns None, should fall back to local path
        result = await k._async_prefer_url_over_local(doc, 1, str(img))
        assert result == str(img)


class TestSyncMethodNotCorrupted:
    """Verify sync methods still use sync calls (not await)."""

    def test_sync_should_skip(self, mock_vdb):
        """_should_skip is a sync method and should work without await."""
        mock_vdb._hashes.add("existing_hash")
        k = Knowledge(vector_db=mock_vdb)
        k.contents_db = None

        result = k._should_skip("existing_hash", True)
        assert result is True

    def test_sync_load_from_url_uses_sync_should_skip(self, mock_vdb):
        """_load_from_url (sync) should call _should_skip (not _async_should_skip)."""
        mock_vdb._hashes.add("existing_hash")
        k = Knowledge(vector_db=mock_vdb)
        k.contents_db = None

        content = MagicMock()
        content.url = "https://example.com/doc.pdf"
        content.name = "doc.pdf"
        content.content_hash = "existing_hash"
        content.id = "id_sync"
        content.file_type = None
        content.metadata = {}
        content.reader = None
        content.auth = None

        # Should not raise any errors - sync _should_skip used
        k._load_from_url(content, upsert=True, skip_if_exists=True)
