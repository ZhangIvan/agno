"""Tests for file type validation utilities in knowledge/utils.py."""

from agno.knowledge.utils import (
    _detect_mime_from_magic_bytes,
    _looks_like_text,
    get_content_type_from_bytes,
    validate_file_type_match,
)


class TestDetectMimeFromMagicBytes:
    def test_pdf_magic_bytes(self):
        data = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        assert _detect_mime_from_magic_bytes(data) == "application/pdf"

    def test_png_magic_bytes(self):
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert _detect_mime_from_magic_bytes(data) == "image/png"

    def test_jpeg_magic_bytes(self):
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        assert _detect_mime_from_magic_bytes(data) == "image/jpeg"

    def test_gif_magic_bytes(self):
        data = b"GIF89a" + b"\x00" * 100
        assert _detect_mime_from_magic_bytes(data) == "image/gif"

    def test_webp_magic_bytes(self):
        data = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 100
        assert _detect_mime_from_magic_bytes(data) == "image/webp"

    def test_zip_magic_bytes(self):
        data = b"PK\x03\x04" + b"\x00" * 100
        assert _detect_mime_from_magic_bytes(data) == "application/zip"

    def test_plain_text(self):
        data = b"Hello, world! This is a plain text file."
        assert _detect_mime_from_magic_bytes(data) == "text/plain"

    def test_json_text(self):
        data = b'{"key": "value", "count": 42}'
        assert _detect_mime_from_magic_bytes(data) == "application/json"

    def test_xml_text(self):
        data = b'<?xml version="1.0"?><root><item>test</item></root>'
        assert _detect_mime_from_magic_bytes(data) == "text/xml"

    def test_empty_data(self):
        assert _detect_mime_from_magic_bytes(b"") == "application/octet-stream"

    def test_short_data(self):
        assert _detect_mime_from_magic_bytes(b"\x00") == "application/octet-stream"

    def test_binary_data_unknown(self):
        data = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f"
        assert _detect_mime_from_magic_bytes(data) == "application/octet-stream"


class TestLooksLikeText:
    def test_plain_ascii(self):
        assert _looks_like_text(b"Hello, world!") is True

    def test_utf8_text(self):
        assert _looks_like_text("你好世界".encode("utf-8")) is True

    def test_binary_data(self):
        assert _looks_like_text(b"\x00\x01\x02\x03\x04\x05") is False

    def test_mixed_newlines(self):
        assert _looks_like_text(b"line1\nline2\r\nline3\ttab") is True

    def test_high_control_char_ratio(self):
        # 50% control chars (non-text)
        data = bytes(range(0, 32)) * 4
        assert _looks_like_text(data) is False


class TestGetContentTypeFromBytes:
    def test_pdf_bytes(self):
        data = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\nrest of document..."
        result = get_content_type_from_bytes(data)
        # python-magic may or may not be installed, so check both paths
        assert result == "application/pdf"

    def test_png_bytes(self):
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        result = get_content_type_from_bytes(data)
        assert result == "image/png"

    def test_empty_bytes(self):
        assert get_content_type_from_bytes(b"") == "application/octet-stream"

    def test_text_bytes(self):
        data = b"This is a plain text document with enough content."
        result = get_content_type_from_bytes(data)
        assert result in ("text/plain", "application/json", "text/xml")


class TestValidateFileTypeMatch:
    def test_matching_pdf(self):
        assert validate_file_type_match("application/pdf", ".pdf") is True

    def test_matching_png(self):
        assert validate_file_type_match("image/png", ".png") is True

    def test_matching_jpeg(self):
        assert validate_file_type_match("image/jpeg", ".jpg") is True
        assert validate_file_type_match("image/jpeg", ".jpeg") is True

    def test_matching_xlsx(self):
        assert (
            validate_file_type_match("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx")
            is True
        )

    def test_matching_csv(self):
        assert validate_file_type_match("text/csv", ".csv") is True

    def test_mismatch_pdf_vs_exe(self):
        # A binary that detects as PDF but claims to be .exe — should fail
        assert validate_file_type_match("application/pdf", ".exe") is False

    def test_mismatch_png_vs_pdf(self):
        assert validate_file_type_match("image/png", ".pdf") is False

    def test_mismatch_zip_vs_pdf(self):
        assert validate_file_type_match("application/zip", ".pdf") is False

    def test_text_plain_compatible_with_many_extensions(self):
        assert validate_file_type_match("text/plain", ".txt") is True
        assert validate_file_type_match("text/plain", ".md") is True
        assert validate_file_type_match("text/plain", ".csv") is True

    def test_octet_stream_is_permissive(self):
        # Unknown content type should not block
        assert validate_file_type_match("application/octet-stream", ".pdf") is True
        assert validate_file_type_match("application/octet-stream", ".exe") is True

    def test_unknown_mime_is_permissive(self):
        assert validate_file_type_match("application/x-custom", ".pdf") is True

    def test_text_mime_subtype_is_permissive(self):
        assert validate_file_type_match("text/x-custom", ".custom") is True

    def test_empty_inputs(self):
        assert validate_file_type_match("", ".pdf") is True
        assert validate_file_type_match("application/pdf", "") is True

    def test_extension_without_dot(self):
        assert validate_file_type_match("application/pdf", "pdf") is True

    def test_mismatch_jpeg_vs_png(self):
        assert validate_file_type_match("image/jpeg", ".png") is False
