"""Unified configuration for image processing and storage operations."""

from dataclasses import dataclass


@dataclass
class ImageProcessingConfig:
    """Configuration for WebP conversion and image storage operations.

    This class centralizes all image processing parameters that were previously
    scattered across multiple reader files (image_reader, pdf_reader, pptx_reader, etc.).

    Attributes:
        webp_quality: WebP encoding quality (1-100). Higher = better quality but larger files.
        webp_method: WebP compression method (0-6). Higher = better compression but slower.
        lossless: If True, use lossless WebP compression. If False, use lossy (smaller files).
        optimize: Apply additional optimization to reduce file size.
        image_dpi: Resolution for rendering PDF/DOCX/PPTX pages to images.
        max_concurrent_uploads: Maximum number of concurrent uploads to cloud storage.
        upload_timeout: Timeout in seconds for individual upload operations.
        upload_retries: Number of retry attempts for failed uploads.
        retry_backoff: Base backoff factor for retries (exponential: backoff^attempt).
    """

    # WebP encoding parameters
    webp_quality: int = 82
    webp_method: int = 4
    lossless: bool = False
    optimize: bool = True

    # Image rendering parameters
    image_dpi: int = 150

    # Upload parameters
    max_concurrent_uploads: int = 10
    upload_timeout: int = 60
    upload_retries: int = 3
    retry_backoff: float = 2.0

    # Cache management
    max_cache_age_days: int = 7
    max_cache_size_mb: int = 500

    def __post_init__(self):
        """Validate configuration values."""
        if not 1 <= self.webp_quality <= 100:
            raise ValueError(f"webp_quality must be between 1 and 100, got {self.webp_quality}")
        if not 0 <= self.webp_method <= 6:
            raise ValueError(f"webp_method must be between 0 and 6, got {self.webp_method}")
        if self.max_concurrent_uploads < 1:
            raise ValueError(f"max_concurrent_uploads must be at least 1, got {self.max_concurrent_uploads}")
        if self.upload_timeout < 1:
            raise ValueError(f"upload_timeout must be at least 1, got {self.upload_timeout}")
        if self.upload_retries < 1:
            raise ValueError(f"upload_retries must be at least 1, got {self.upload_retries}")


# Default configuration instance
DEFAULT_IMAGE_CONFIG = ImageProcessingConfig()
