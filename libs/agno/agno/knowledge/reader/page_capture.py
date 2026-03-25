import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional

from agno.knowledge.utils.image_config import DEFAULT_IMAGE_CONFIG, ImageProcessingConfig
from agno.utils.log import log_debug, log_error


def get_default_pages_cache_dir() -> Path:
    """Returns ~/.agno/page_cache/ as the default directory for page images."""
    cache_dir = Path.home() / ".agno" / "page_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def capture_pdf_pages(
    pdf_path: str,
    output_dir: str,
    dpi: Optional[int] = None,
    optimize: bool = True,
    config: Optional[ImageProcessingConfig] = None,
) -> Dict[int, str]:
    """Render each page of a PDF to a WebP image.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory to save page images.
        dpi: Resolution for rendering. If None, uses config.image_dpi (default 150).
        optimize: If True, apply WebP optimization to reduce file size (default True).
        config: ImageProcessingConfig instance. If None, uses DEFAULT_IMAGE_CONFIG.

    Returns:
        Dict mapping 1-based page number to image file path.
    """
    cfg = config or DEFAULT_IMAGE_CONFIG
    effective_dpi = dpi if dpi is not None else cfg.image_dpi

    try:
        import fitz  # pymupdf
        from PIL import Image
    except ImportError as e:
        if "fitz" in str(e):
            raise ImportError("`pymupdf` not installed. Please install it via `pip install pymupdf`.")
        if "PIL" in str(e):
            raise ImportError("`Pillow` not installed. Please install it via `pip install Pillow`.")
        raise

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    page_images: Dict[int, str] = {}
    try:
        doc = fitz.open(pdf_path)
        matrix = fitz.Matrix(effective_dpi / 72, effective_dpi / 72)
        for page_index in range(len(doc)):
            page = doc[page_index]
            pix = page.get_pixmap(matrix=matrix)
            page_number = page_index + 1
            image_path = str(output_path / f"page_{page_number}.webp")

            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

            if optimize:
                img.save(
                    image_path,
                    "WebP",
                    quality=cfg.webp_quality,
                    lossless=cfg.lossless,
                    method=cfg.webp_method,
                    optimize=cfg.optimize,
                )
            else:
                img.save(image_path, "WebP", quality=85)
            page_images[page_number] = image_path
            log_debug(f"Captured page {page_number} → {image_path} ({pix.width}x{pix.height})")
        doc.close()
    except Exception as e:
        log_error(f"Error capturing PDF pages from {pdf_path}: {e}")
        raise

    return page_images


def _convert_to_pdf_libreoffice(input_path: str, output_dir: str) -> str:
    """Convert a document (DOCX, PPTX, etc.) to PDF using LibreOffice headless.

    Args:
        input_path: Path to the input document.
        output_dir: Directory to write the converted PDF.

    Returns:
        Path to the output PDF file.

    Raises:
        ValueError: If LibreOffice is not found or conversion fails.
    """
    import shutil

    libreoffice_bin = shutil.which("libreoffice") or shutil.which("soffice")
    if libreoffice_bin is None:
        raise ValueError(
            "LibreOffice not found. Please install LibreOffice to enable DOCX/PPTX page capture. "
            "On Ubuntu/Debian: `sudo apt-get install libreoffice`. "
            "On macOS: `brew install libreoffice`."
        )

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    cmd = [
        libreoffice_bin,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_path),
        input_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise ValueError(f"LibreOffice conversion failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise ValueError("LibreOffice conversion timed out (120s).")

    # LibreOffice outputs <filename>.pdf in output_dir
    input_stem = Path(input_path).stem
    pdf_output = output_path / f"{input_stem}.pdf"
    if not pdf_output.exists():
        raise ValueError(f"LibreOffice conversion did not produce expected PDF: {pdf_output}")

    log_debug(f"Converted {input_path} → {pdf_output}")
    return str(pdf_output)


def capture_pptx_slides(
    pptx_path: str,
    output_dir: str,
    dpi: Optional[int] = None,
    config: Optional[ImageProcessingConfig] = None,
) -> Dict[int, str]:
    """Render each slide of a PPTX to a WebP image via LibreOffice→PDF→pymupdf.

    Args:
        pptx_path: Path to the PPTX file.
        output_dir: Directory to save slide images.
        dpi: Resolution for rendering. If None, uses config.image_dpi (default 150).
        config: ImageProcessingConfig instance. If None, uses DEFAULT_IMAGE_CONFIG.

    Returns:
        Dict mapping 1-based slide number to image file path.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = _convert_to_pdf_libreoffice(pptx_path, tmp_dir)
        return capture_pdf_pages(pdf_path, output_dir, dpi=dpi, config=config)


def capture_docx_pages(
    docx_path: str,
    output_dir: str,
    dpi: Optional[int] = None,
    config: Optional[ImageProcessingConfig] = None,
) -> Dict[int, str]:
    """Render each page of a DOCX to a WebP image via LibreOffice→PDF→pymupdf.

    Args:
        docx_path: Path to the DOCX file.
        output_dir: Directory to save page images.
        dpi: Resolution for rendering. If None, uses config.image_dpi (default 150).
        config: ImageProcessingConfig instance. If None, uses DEFAULT_IMAGE_CONFIG.

    Returns:
        Dict mapping 1-based page number to image file path.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = _convert_to_pdf_libreoffice(docx_path, tmp_dir)
        return capture_pdf_pages(pdf_path, output_dir, dpi=dpi, config=config)


def get_page_cache_dir(base_dir: Optional[str], doc_name: str) -> str:
    """Get (and create) a per-document subdirectory inside the page cache.

    Args:
        base_dir: Base cache directory; uses default if None.
        doc_name: Document name used as subdirectory name.

    Returns:
        Path string to the per-document cache directory.
    """
    if base_dir:
        cache = Path(base_dir) / doc_name
    else:
        cache = get_default_pages_cache_dir() / doc_name
    cache.mkdir(parents=True, exist_ok=True)
    return str(cache)


def convert_to_webp(
    image_source: str,
    output_path: str,
    config: Optional[ImageProcessingConfig] = None,
) -> str:
    """Convert an image file to WebP format.

    This is a unified function for WebP conversion used by various readers.

    Args:
        image_source: Path to the source image file.
        output_path: Path where the WebP image will be saved.
        config: ImageProcessingConfig instance. If None, uses DEFAULT_IMAGE_CONFIG.

    Returns:
        Path to the output WebP file.

    Raises:
        ImportError: If Pillow is not installed.
        IOError: If the source image cannot be read or output cannot be written.
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("`Pillow` not installed. Please install it via `pip install Pillow`.")

    cfg = config or DEFAULT_IMAGE_CONFIG

    img = Image.open(image_source).convert("RGB")
    img.save(
        output_path,
        "WebP",
        quality=cfg.webp_quality,
        method=cfg.webp_method,
        lossless=cfg.lossless,
        optimize=cfg.optimize,
    )

    return output_path
