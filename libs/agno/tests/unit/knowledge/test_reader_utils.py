"""Unit tests for agno.knowledge.reader.utils."""

from io import BytesIO
from pathlib import Path

import pytest

from agno.knowledge.reader.utils import temp_file_from_bytesio


class TestTempFileFromBytesIO:
    """Tests for temp_file_from_bytesio context manager."""

    def test_str_path_yields_as_is(self, tmp_path: Path):
        file_path = str(tmp_path / "test.txt")
        Path(file_path).write_text("hello")
        with temp_file_from_bytesio(file_path, ".txt") as result:
            assert result == file_path
            assert Path(result).exists()

    def test_path_object_yields_str(self, tmp_path: Path):
        file_path = tmp_path / "test.txt"
        file_path.write_text("hello")
        with temp_file_from_bytesio(file_path, ".txt") as result:
            assert result == str(file_path)
            assert Path(result).exists()

    def test_bytesio_creates_temp_file(self):
        data = b"hello world"
        bio = BytesIO(data)
        with temp_file_from_bytesio(bio, ".bin") as result:
            assert result is not None
            assert Path(result).exists()
            assert Path(result).read_bytes() == data
        # Temp file cleaned up after exit
        assert not Path(result).exists()

    def test_bytesio_seek_position_restored(self):
        """Verify the BytesIO position is reset after the context manager writes."""
        data = b"seek test"
        bio = BytesIO(data)
        bio.seek(5)
        with temp_file_from_bytesio(bio, ".bin") as _:
            pass
        # After context manager exits, position should be at 0
        assert bio.tell() == 0

    def test_bytesio_cleanup_on_exception(self):
        """Temp file should be cleaned up even if an exception occurs inside the with block."""
        data = b"cleanup test"
        bio = BytesIO(data)
        result = None
        with pytest.raises(RuntimeError):
            with temp_file_from_bytesio(bio, ".bin") as result:
                assert result is not None
                assert Path(result).exists()
                raise RuntimeError("boom")
        # Temp file should still be cleaned up
        if result:
            assert not Path(result).exists()
