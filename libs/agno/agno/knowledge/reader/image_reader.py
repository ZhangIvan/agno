import asyncio
import os
import shutil
from pathlib import Path
from typing import IO, Any, List, Optional, Union

from agno.knowledge.document.base import Document
from agno.knowledge.reader.base import Reader
from agno.knowledge.types import ContentType
from agno.utils.log import log_debug, log_warning

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"}


class ImageReader(Reader):
    """Reader for direct image file uploads.

    Copies the image into the page-cache directory and returns a single
    ``page_image`` Document so that the standard OSS-upload and multimodal
    embedding pipeline handles it exactly like a page extracted from a PDF or
    PPTX.

    Supported formats: PNG, JPG, JPEG, GIF, WEBP, BMP, TIFF.
    """

    def __init__(
        self,
        pages_cache_dir: Optional[str] = None,
        **kwargs,
    ):
        self.pages_cache_dir = pages_cache_dir or os.getenv("AGNO_PAGE_CACHE_DIR")
        # Images are not text-chunkable; disable chunking by default.
        kwargs.setdefault("chunking_strategy", None)
        super().__init__(**kwargs)

    @classmethod
    def get_supported_content_types(cls) -> List[ContentType]:
        return [
            ContentType.PNG,
            ContentType.JPG,
            ContentType.JPEG,
            ContentType.GIF,
            ContentType.WEBP,
            ContentType.BMP,
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_cache_copy(self, src: Union[str, IO[Any]], doc_name: str, img_suffix: str) -> tuple:
        """Copy *src* into the per-document page-cache dir.

        Returns (cache_path, cache_dir).
        """
        from agno.knowledge.reader.page_capture import get_page_cache_dir

        cache_dir = get_page_cache_dir(self.pages_cache_dir, doc_name)
        cache_path = os.path.join(cache_dir, f"page_1{img_suffix}")

        if isinstance(src, str):
            shutil.copy2(src, cache_path)
        else:
            if hasattr(src, "seek"):
                src.seek(0)
            with open(cache_path, "wb") as fout:
                shutil.copyfileobj(src, fout)
            if hasattr(src, "seek"):
                src.seek(0)

        return cache_path, cache_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self, file: Union[Path, IO[Any]], name: Optional[str] = None, **kwargs) -> List[Document]:
        """Read an image file and return a single ``page_image`` Document."""
        try:
            if isinstance(file, Path):
                if not file.exists():
                    raise FileNotFoundError(f"Could not find file: {file}")
                log_debug(f"Reading image: {file}")
                doc_name = name or file.stem
                img_suffix = file.suffix.lower() or ".png"
                cache_path, cache_dir = self._make_cache_copy(str(file), doc_name, img_suffix)
            else:
                raw_name = name or getattr(file, "name", "image.png")
                base = os.path.basename(raw_name)
                doc_name = base.rsplit(".", 1)[0] if "." in base else base
                img_suffix = os.path.splitext(base)[1].lower() or ".png"
                cache_path, cache_dir = self._make_cache_copy(file, doc_name, img_suffix)

            return [
                Document(
                    name=doc_name,
                    content="",
                    meta_data={
                        "doc_type": "page_image",
                        "page_number": 1,
                        "total_pages": 1,
                        "page_image_path": cache_path,
                        "pages_cache_dir": cache_dir,
                    },
                )
            ]
        except Exception as e:
            log_warning(f"ImageReader.read failed: {e}")
            return []

    async def async_read(self, file: Union[Path, IO[Any]], name: Optional[str] = None, **kwargs) -> List[Document]:
        """Async version — delegates to ``read()`` via a thread."""
        return await asyncio.to_thread(self.read, file, name)
