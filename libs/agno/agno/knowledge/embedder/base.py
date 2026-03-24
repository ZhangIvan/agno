from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class Embedder:
    """Base class for managing embedders"""

    dimensions: Optional[int] = 1536
    enable_batch: bool = False
    batch_size: int = 100  # Number of texts to process in each API call

    def get_embedding(self, text: str) -> List[float]:
        raise NotImplementedError

    def get_embedding_and_usage(self, text: str) -> Tuple[List[float], Optional[Dict]]:
        raise NotImplementedError

    async def async_get_embedding(self, text: str) -> List[float]:
        raise NotImplementedError

    async def async_get_embedding_and_usage(self, text: str) -> Tuple[List[float], Optional[Dict]]:
        raise NotImplementedError

    def get_image_embedding(self, image_path: str) -> Optional[List[float]]:
        """Get embedding for an image file. Returns None if not supported by this embedder."""
        raise NotImplementedError

    async def async_get_image_embedding(self, image_path: str) -> Optional[List[float]]:
        """Async get embedding for an image file. Returns None if not supported by this embedder."""
        raise NotImplementedError
