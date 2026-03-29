from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

from pydantic import BaseModel


# Supported image file extensions for knowledge readers
SUPPORTED_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif"})


@runtime_checkable
class PageImageStorage(Protocol):
    """Protocol for page image storage backends (e.g., OSS, S3, TOS)."""

    def upload(self, file_path: str, object_key: str) -> Optional[str]: ...
    def sign_url(self, object_key: str, expires: int = 3600) -> Optional[str]: ...

    async def async_upload(self, file_path: str, object_key: str) -> Optional[str]: ...
    async def async_sign_url(self, object_key: str, expires: int = 3600) -> Optional[str]: ...


class DocType(str, Enum):
    """Constants for document types used in knowledge base."""

    PAGE_IMAGE = "page_image"
    TEXT_CHUNK = "text_chunk"


class ContentType(str, Enum):
    """Enum for content types supported by knowledge readers."""

    # Generic types
    FILE = "file"
    URL = "url"
    TEXT = "text"
    TOPIC = "topic"
    YOUTUBE = "youtube"

    # Document file extensions
    PDF = ".pdf"
    TXT = ".txt"
    MARKDOWN = ".md"
    DOCX = ".docx"
    DOC = ".doc"
    PPTX = ".pptx"
    JSON = ".json"

    # Spreadsheet file extensions
    CSV = ".csv"
    XLSX = ".xlsx"
    XLS = ".xls"

    # Image file extensions
    PNG = ".png"
    JPG = ".jpg"
    JPEG = ".jpeg"
    GIF = ".gif"
    WEBP = ".webp"
    BMP = ".bmp"
    TIFF = ".tiff"
    TIF = ".tif"


def get_content_type_enum(content_type_str: str) -> ContentType:
    """Convert a content type string to ContentType enum."""
    return ContentType(content_type_str)


class KnowledgeContentOrigin(str, Enum):
    """Origin of knowledge content for processing routing."""

    PATH = "path"
    URL = "url"
    TOPIC = "topic"
    CONTENT = "content"


class KnowledgeFilter(BaseModel):
    key: str
    value: Any
