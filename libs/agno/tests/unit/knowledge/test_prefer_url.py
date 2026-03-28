"""Unit tests for _prefer_url_over_local JIT upload logic."""

from unittest.mock import MagicMock

import pytest

from agno.knowledge.knowledge import Knowledge


@pytest.fixture
def knowledge_with_storage():
    """Knowledge instance with a mock page_image_storage."""
    k = Knowledge()
    storage = MagicMock()
    storage.upload.return_value = "https://oss.example.com/img/page_1.png"
    storage.sign_url.return_value = "https://oss.example.com/img/page_1.png?signed=abc"
    k.page_image_storage = storage
    k.url_signature_expires = 3600
    return k, storage


class TestPreferUrlOverLocal:
    def test_http_url_returned_as_is(self, knowledge_with_storage):
        k, storage = knowledge_with_storage
        doc = MagicMock(content_id="cid", name="test")

        result = k._prefer_url_over_local(doc, 1, "https://example.com/img.png")
        assert result == "https://example.com/img.png"
        storage.upload.assert_not_called()

    def test_no_storage_returns_local(self):
        k = Knowledge()
        k.page_image_storage = None
        doc = MagicMock(content_id="cid", name="test")

        result = k._prefer_url_over_local(doc, 1, "/tmp/page_1.png")
        assert result == "/tmp/page_1.png"

    def test_nonexistent_file_returns_local(self, knowledge_with_storage):
        k, storage = knowledge_with_storage
        doc = MagicMock(content_id="cid", name="test")

        result = k._prefer_url_over_local(doc, 1, "/nonexistent/page_1.png")
        assert result == "/nonexistent/page_1.png"
        storage.upload.assert_not_called()

    def test_local_file_uploaded_and_signed(self, knowledge_with_storage, tmp_path):
        k, storage = knowledge_with_storage
        img = tmp_path / "page_1.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        doc = MagicMock(content_id="cid", name="test")

        result = k._prefer_url_over_local(doc, 1, str(img))
        assert result == "https://oss.example.com/img/page_1.png?signed=abc"
        storage.upload.assert_called_once()
        storage.sign_url.assert_called_once()

    def test_upload_failure_falls_back_to_local(self, knowledge_with_storage, tmp_path):
        k, storage = knowledge_with_storage
        storage.upload.side_effect = RuntimeError("OSS unavailable")
        img = tmp_path / "page_2.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        doc = MagicMock(content_id="cid", name="test")

        result = k._prefer_url_over_local(doc, 2, str(img))
        assert result == str(img)

    def test_sign_url_failure_falls_back_to_local(self, knowledge_with_storage, tmp_path):
        k, storage = knowledge_with_storage
        storage.sign_url.side_effect = RuntimeError("signing failed")
        img = tmp_path / "page_3.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        doc = MagicMock(content_id="cid", name="test")

        result = k._prefer_url_over_local(doc, 3, str(img))
        assert result == str(img)

    def test_upload_returns_none_falls_back(self, knowledge_with_storage, tmp_path):
        k, storage = knowledge_with_storage
        storage.upload.return_value = None
        img = tmp_path / "page_4.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        doc = MagicMock(content_id="cid", name="test")

        result = k._prefer_url_over_local(doc, 4, str(img))
        assert result == str(img)
