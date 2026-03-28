"""Unit tests for reader_factory image extension support."""

import pytest

from agno.knowledge.reader.image_reader import ImageReader
from agno.knowledge.reader.reader_factory import ReaderFactory
from agno.knowledge.types import SUPPORTED_IMAGE_EXTENSIONS


class TestReaderFactoryImageExtensions:
    """Ensure all SUPPORTED_IMAGE_EXTENSIONS are recognized by ReaderFactory."""

    @pytest.mark.parametrize("ext", list(SUPPORTED_IMAGE_EXTENSIONS))
    def test_extension_produces_image_reader(self, ext):
        reader = ReaderFactory.get_reader_for_extension(ext)
        assert isinstance(reader, ImageReader), f"Extension {ext} should produce ImageReader, got {type(reader)}"

    def test_all_supported_extensions_covered(self):
        """Verify that SUPPORTED_IMAGE_EXTENSIONS frozenset matches what ReaderFactory handles."""
        for ext in SUPPORTED_IMAGE_EXTENSIONS:
            reader = ReaderFactory.get_reader_for_extension(ext)
            assert isinstance(reader, ImageReader)
