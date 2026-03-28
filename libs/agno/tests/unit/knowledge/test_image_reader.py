"""Unit tests for agno.knowledge.reader.image_reader."""

from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

from agno.knowledge.reader.image_reader import ImageReader
from agno.knowledge.types import ContentType


@pytest.fixture
def reader():
    return ImageReader()


class TestImageReaderSupportedContentTypes:
    def test_returns_list(self, reader):
        types = reader.get_supported_content_types()
        assert isinstance(types, list)
        assert len(types) > 0

    def test_includes_common_formats(self, reader):
        types = reader.get_supported_content_types()
        assert ContentType.PNG in types
        assert ContentType.JPG in types


class TestImageReaderRead:
    def test_read_path_not_found(self, reader):
        """ImageReader catches FileNotFoundError internally and returns empty list."""
        docs = reader.read(Path("/nonexistent/image.png"))
        assert docs == []

    @patch("agno.knowledge.reader.image_reader.ImageReader._to_webp")
    def test_read_bytesio(self, mock_to_webp, reader):
        """Test reading from BytesIO source."""
        mock_to_webp.return_value = ("/tmp/test.webp", "/tmp/cache_dir")
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # minimal PNG header
        bio = BytesIO(data)
        bio.name = "test.png"

        docs = reader.read(bio)
        assert len(docs) == 1
        assert docs[0].meta_data.get("doc_type") == "page_image"
        assert docs[0].meta_data.get("page_number") == 1

    @patch("agno.knowledge.reader.image_reader.ImageReader._to_webp")
    def test_read_path_exists(self, mock_to_webp, reader, tmp_path):
        """Test reading from an existing Path source."""
        mock_to_webp.return_value = ("/tmp/test.webp", "/tmp/cache_dir")
        img_file = tmp_path / "photo.jpg"
        img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # JPEG header

        docs = reader.read(img_file)
        assert len(docs) == 1
        assert docs[0].name == "photo"
        assert docs[0].meta_data.get("doc_type") == "page_image"
