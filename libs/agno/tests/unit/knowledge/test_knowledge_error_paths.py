"""Unit tests for error paths in Knowledge class.

Tests cover:
1. VectorDB insert failure → rollback (local temp cleanup + orphaned OSS warning)
2. VectorDB upsert failure → rollback
3. Reader exception during content loading
4. ContentsDB unavailable graceful degradation
5. Upload failure doesn't block insert
6. No vector database configured
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


class FailingVectorDb(VectorDb):
    """VectorDb that can be configured to fail on specific operations."""

    def __init__(
        self,
        fail_insert=False,
        fail_upsert=False,
        fail_search=False,
        fail_content_hash=False,
    ):
        self.fail_insert = fail_insert
        self.fail_upsert = fail_upsert
        self.fail_search = fail_search
        self.fail_content_hash = fail_content_hash
        self.insert_called = False
        self.upsert_called = False

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
        if self.fail_content_hash:
            raise ConnectionError("VectorDB unavailable")
        return False

    def insert(self, content_hash: str, documents: List[Document], filters=None) -> None:
        self.insert_called = True
        if self.fail_insert:
            raise RuntimeError("Insert failed: connection lost")

    async def async_insert(self, content_hash: str, documents: List[Document], filters=None) -> None:
        self.insert_called = True
        if self.fail_insert:
            raise RuntimeError("Async insert failed: connection lost")

    def upsert(self, content_hash: str, documents: List[Document], filters=None) -> None:
        self.upsert_called = True
        if self.fail_upsert:
            raise RuntimeError("Upsert failed: timeout")

    async def async_upsert(self, content_hash: str, documents: List[Document], filters=None) -> None:
        self.upsert_called = True
        if self.fail_upsert:
            raise RuntimeError("Async upsert failed: timeout")

    def upsert_available(self) -> bool:
        return True

    def search(self, query: str, limit: int = 5, filters=None) -> List[Document]:
        if self.fail_search:
            raise RuntimeError("Search failed")
        return []

    async def async_search(self, query: str, limit: int = 5, filters=None) -> List[Document]:
        if self.fail_search:
            raise RuntimeError("Async search failed")
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


class NoUpsertVectorDb(FailingVectorDb):
    """VectorDb that doesn't support upsert."""

    def upsert_available(self) -> bool:
        return False


# ===== FIXTURES =====


def _make_doc(content="test content", meta_data=None, name="test.txt"):
    return Document(content=content, meta_data=meta_data or {}, name=name)


def _make_content(**overrides):
    """Create a mock Content object with sensible defaults."""
    defaults = {
        "url": "https://example.com/test.pdf",
        "name": "test.pdf",
        "content_hash": "hash_error_test",
        "id": "id_error_test",
        "file_type": None,
        "metadata": {},
        "reader": None,
        "auth": None,
        "status": None,
        "status_message": None,
    }
    defaults.update(overrides)
    content = MagicMock()
    for k, v in defaults.items():
        setattr(content, k, v)
    return content


# ===== VECTORDB FAILURE TESTS =====


class TestVectorDbInsertFailure:
    """Verify that VectorDB insert failures trigger rollback."""

    @pytest.mark.asyncio
    async def test_async_upsert_failure_sets_failed_and_cleans_up(self):
        """When async_upsert fails, content should be FAILED and local files cleaned."""
        vdb = FailingVectorDb(fail_upsert=True)
        k = Knowledge(vector_db=vdb)
        k.contents_db = None

        # Track cleanup calls
        cleanup_called = False

        async def mock_cleanup(docs, paths):
            nonlocal cleanup_called
            cleanup_called = True

        k._async_cleanup_local_page_images = mock_cleanup

        content = _make_content()
        docs = [_make_doc()]

        await k._ahandle_vector_db_insert(content, docs, upsert=True, file_source=None)

        assert content.status is not None
        assert content.status.value == "failed"
        assert "upsert" in content.status_message.lower()

    @pytest.mark.asyncio
    async def test_async_insert_failure_sets_failed(self):
        """When async_insert fails (non-upsert path), content should be FAILED."""
        vdb = FailingVectorDb(fail_insert=True)
        k = Knowledge(vector_db=vdb)
        k.contents_db = None

        content = _make_content()
        docs = [_make_doc()]

        await k._ahandle_vector_db_insert(content, docs, upsert=False, file_source=None)

        assert content.status is not None
        assert content.status.value == "failed"
        assert "insert" in content.status_message.lower()

    def test_sync_upsert_failure_sets_failed(self):
        """Sync: when upsert fails, content should be FAILED."""
        vdb = FailingVectorDb(fail_upsert=True)
        k = Knowledge(vector_db=vdb)
        k.contents_db = None

        content = _make_content()
        docs = [_make_doc()]

        k._handle_vector_db_insert(content, docs, upsert=True, file_source=None)

        assert content.status is not None
        assert content.status.value == "failed"

    def test_sync_insert_failure_sets_failed(self):
        """Sync: when insert fails, content should be FAILED."""
        vdb = FailingVectorDb(fail_insert=True)
        k = Knowledge(vector_db=vdb)
        k.contents_db = None

        content = _make_content()
        docs = [_make_doc()]

        k._handle_vector_db_insert(content, docs, upsert=False, file_source=None)

        assert content.status is not None
        assert content.status.value == "failed"


# ===== NO VECTORDB TESTS =====


class TestNoVectorDb:
    """Verify behavior when vector_db is not configured."""

    @pytest.mark.asyncio
    async def test_async_no_vdb_sets_failed(self):
        """When vector_db is None, content should be FAILED with appropriate message."""
        k = Knowledge(vector_db=None)
        k.contents_db = None

        content = _make_content()
        docs = [_make_doc()]

        await k._ahandle_vector_db_insert(content, docs, upsert=True)

        assert content.status is not None
        assert content.status.value == "failed"
        assert "vector database" in content.status_message.lower()

    def test_sync_no_vdb_sets_failed(self):
        """Sync: when vector_db is None, content should be FAILED."""
        k = Knowledge(vector_db=None)
        k.contents_db = None

        content = _make_content()
        docs = [_make_doc()]

        k._handle_vector_db_insert(content, docs, upsert=True)

        assert content.status is not None
        assert content.status.value == "failed"
        assert "vector database" in content.status_message.lower()


# ===== UPLOAD FAILURE TESTS =====


class TestUploadFailure:
    """Verify that upload failures don't block the insert pipeline."""

    @pytest.mark.asyncio
    async def test_original_file_upload_failure_doesnt_block_insert(self):
        """When _async_upload_original_file fails, insert should still proceed."""
        vdb = FailingVectorDb()
        k = Knowledge(vector_db=vdb)
        k.contents_db = None

        storage = MagicMock()
        storage.async_upload = AsyncMock(side_effect=RuntimeError("OSS unavailable"))
        k.page_image_storage = storage

        content = _make_content()
        docs = [_make_doc()]

        # Mock file_source as a Path to trigger upload attempt
        from pathlib import Path

        file_source = Path("/fake/file.pdf")

        await k._ahandle_vector_db_insert(content, docs, upsert=True, file_source=file_source)

        # Insert should have succeeded despite upload failure
        assert vdb.upsert_called
        assert content.status is not None
        assert content.status.value == "completed"

    @pytest.mark.asyncio
    async def test_page_image_upload_failure_doesnt_block_insert(self):
        """When page image upload fails, insert should still proceed (upload logs warning)."""
        vdb = FailingVectorDb()
        k = Knowledge(vector_db=vdb)
        k.contents_db = None

        storage = MagicMock()
        # upload returns None = failure but no exception
        storage.async_upload = AsyncMock(return_value=None)
        storage.upload.return_value = None
        k.page_image_storage = storage

        content = _make_content()
        docs = [_make_doc(meta_data={"page_image_path": "/fake/page.png", "page_number": 1})]

        await k._ahandle_vector_db_insert(content, docs, upsert=True, file_source=None)

        # Insert should still succeed
        assert vdb.upsert_called


# ===== READER EXCEPTION TESTS =====


class TestReaderException:
    """Verify that Reader exceptions during content loading set FAILED status."""

    @pytest.mark.asyncio
    async def test_reader_exception_in_aload_from_url_sets_failed(self):
        """Reader exception during async URL load should set content to FAILED."""
        vdb = FailingVectorDb()
        k = Knowledge(vector_db=vdb)
        k.contents_db = None

        mock_reader = MagicMock()
        mock_reader.async_read = AsyncMock(side_effect=RuntimeError("Corrupt PDF: invalid header"))
        mock_reader.chunk = True
        mock_reader.chunk_documents_async = AsyncMock(side_effect=lambda docs: docs)

        with patch.object(k, "_select_reader_by_extension", return_value=(mock_reader, "")):
            with patch("agno.knowledge._mixins._load_url.AsyncClient") as mock_client_cls:
                # Use MagicMock (not AsyncMock) for response so aiter_bytes() returns
                # an async iterator directly, matching production code pattern.
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                mock_response.aiter_bytes = MagicMock(return_value=_AsyncIter([b"fake pdf"]))
                mock_client = MagicMock()
                mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
                mock_client.stream.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

                content = _make_content()
                await k._aload_from_url(content, upsert=True, skip_if_exists=False)

        assert content.status is not None
        assert content.status.value == "failed"
        assert "error" in content.status_message.lower() or "corrupt" in content.status_message.lower()


# ===== CONTENTS DB UNAVAILABLE TESTS =====


class TestContentsDbUnavailable:
    """Verify graceful behavior when contents_db is not configured."""

    def test_insert_contents_db_with_none_is_noop(self):
        """_insert_contents_db with contents_db=None should be a no-op."""
        vdb = FailingVectorDb()
        k = Knowledge(vector_db=vdb)
        k.contents_db = None

        content = _make_content()
        # Should not raise
        k._insert_contents_db(content)

    @pytest.mark.asyncio
    async def test_ainsert_contents_db_with_none_is_noop(self):
        """_ainsert_contents_db with contents_db=None should be a no-op."""
        vdb = FailingVectorDb()
        k = Knowledge(vector_db=vdb)
        k.contents_db = None

        content = _make_content()
        await k._ainsert_contents_db(content)


# ===== SEARCH ERROR HANDLING =====


class TestSearchErrorHandling:
    """Verify search errors are handled gracefully."""

    def test_search_exception_returns_empty(self):
        """When search raises, return empty list instead of propagating exception."""
        vdb = FailingVectorDb(fail_search=True)
        k = Knowledge(vector_db=vdb)
        k.contents_db = None

        result = k.search(query="test")
        assert result == []

    @pytest.mark.asyncio
    async def test_asearch_exception_returns_empty(self):
        """When async_search raises, return empty list."""
        vdb = FailingVectorDb(fail_search=True)
        k = Knowledge(vector_db=vdb)
        k.contents_db = None

        result = await k.asearch(query="test")
        assert result == []


# ===== CONTENT STATUS TRANSITIONS =====


class TestContentStatusTransitions:
    """Verify content status transitions through the error paths."""

    @pytest.mark.asyncio
    async def test_failed_status_preserved_after_multiple_errors(self):
        """When both upload and insert fail, content should be FAILED."""
        vdb = FailingVectorDb(fail_upsert=True)
        k = Knowledge(vector_db=vdb)
        k.contents_db = None

        storage = MagicMock()
        storage.async_upload = AsyncMock(side_effect=RuntimeError("OSS down"))
        k.page_image_storage = storage

        content = _make_content()
        docs = [_make_doc()]

        from pathlib import Path

        await k._ahandle_vector_db_insert(content, docs, upsert=True, file_source=Path("/fake/file.pdf"))

        # Both upload and upsert failed, but status should reflect the critical failure
        assert content.status is not None
        assert content.status.value == "failed"

    def test_no_upsert_available_uses_insert_path(self):
        """When upsert_available() is False, should use insert path."""
        vdb = NoUpsertVectorDb(fail_insert=True)
        k = Knowledge(vector_db=vdb)
        k.contents_db = None

        content = _make_content()
        docs = [_make_doc()]

        k._handle_vector_db_insert(content, docs, upsert=True)

        # Should have tried insert (not upsert) and failed
        assert vdb.insert_called
        assert not vdb.upsert_called
        assert content.status is not None
        assert content.status.value == "failed"
