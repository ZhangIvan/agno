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

    def get_image_embedding_and_usage(self, image_path: str) -> Tuple[Optional[List[float]], Optional[Dict]]:
        """Get embedding + token usage for an image. Subclasses override to return real usage."""
        return self.get_image_embedding(image_path), None

    async def async_get_image_embedding(self, image_path: str) -> Optional[List[float]]:
        """Async get embedding for an image file. Returns None if not supported by this embedder."""
        raise NotImplementedError

    async def async_get_image_embedding_and_usage(
        self, image_path: str
    ) -> Tuple[Optional[List[float]], Optional[Dict]]:
        """Async get embedding + token usage for an image. Subclasses override to return real usage."""
        return await self.async_get_image_embedding(image_path), None
