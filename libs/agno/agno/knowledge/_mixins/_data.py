"""Data conversion and hashing helpers for the Knowledge class.

These are pure data functions that convert between Content, KnowledgeRow,
and hash representations. They have minimal cross-dependencies.
"""

import hashlib
import time
from typing import Any, Optional

from agno.db.schemas.knowledge import KnowledgeRow
from agno.knowledge.content import Content, ContentStatus
from agno.utils.log import log_debug, log_warning


class _KnowledgeDataMixin:
    """Data conversion and hashing methods extracted from Knowledge."""

    def _build_content_hash(self, content: Content) -> str:
        """
        Build the content hash from the content.

        For URLs and paths, includes the name and description in the hash if provided
        to ensure unique content with the same URL/path but different names/descriptions
        get different hashes.

        Hash format:
        - URL with name and description: hash("{name}:{description}:{url}")
        - URL with name only: hash("{name}:{url}")
        - URL with description only: hash("{description}:{url}")
        - URL without name/description: hash("{url}") (backward compatible)
        - Same logic applies to paths
        """
        hash_parts = []
        if content.name:
            hash_parts.append(content.name)
        if content.description:
            hash_parts.append(content.description)

        if content.path:
            hash_parts.append(str(content.path))
        elif content.url:
            hash_parts.append(content.url)
        elif content.file_data and content.file_data.content:
            # For file_data, always add filename, type, size, or content for uniqueness
            if content.file_data.filename:
                hash_parts.append(content.file_data.filename)
            elif content.file_data.type:
                hash_parts.append(content.file_data.type)
            elif content.file_data.size is not None:
                hash_parts.append(str(content.file_data.size))
            else:
                # Fallback: use the content for uniqueness
                # Include type information to distinguish str vs bytes
                content_type = "str" if isinstance(content.file_data.content, str) else "bytes"
                content_bytes = (
                    content.file_data.content.encode()
                    if isinstance(content.file_data.content, str)
                    else content.file_data.content
                )
                content_hash = hashlib.sha256(content_bytes).hexdigest()[:16]  # Use first 16 chars
                hash_parts.append(f"{content_type}:{content_hash}")
        elif content.topics and len(content.topics) > 0:
            topic = content.topics[0]
            reader = type(content.reader).__name__ if content.reader else "unknown"
            hash_parts.append(f"{topic}-{reader}")
        else:
            # Fallback for edge cases
            import random
            import string

            fallback = (
                content.name
                or content.id
                or ("unknown_content" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6)))
            )
            hash_parts.append(fallback)

        hash_input = ":".join(hash_parts)
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def _build_document_content_hash(self, document, content: Content) -> str:
        """
        Build content hash for a specific document.

        Used for multi-page readers (like WebsiteReader) where each crawled page
        should have its own unique content hash based on its actual URL.

        Args:
            document: The document to build the hash for
            content: The original content object (for fallback name/description)

        Returns:
            A unique hash string for this specific document
        """
        hash_parts = []

        if content.name:
            hash_parts.append(content.name)
        if content.description:
            hash_parts.append(content.description)

        # Use document's own URL if available (set by WebsiteReader)
        doc_url = document.meta_data.get("url") if document.meta_data else None
        if doc_url:
            hash_parts.append(str(doc_url))
        elif content.url:
            hash_parts.append(content.url)
        elif content.path:
            hash_parts.append(str(content.path))
        else:
            # Fallback: use content hash for uniqueness
            hash_parts.append(hashlib.sha256(document.content.encode()).hexdigest()[:16])

        hash_input = ":".join(hash_parts)
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def _ensure_string_field(self, value: Any, field_name: str, default: str = "") -> str:
        """
        Safely ensure a field is a string, handling various edge cases.

        Args:
            value: The value to convert to string
            field_name: Name of the field for logging purposes
            default: Default string value if conversion fails

        Returns:
            str: A safe string value
        """
        # Handle None/falsy values
        if value is None or value == "":
            return default

        # Handle unexpected list types (the root cause of our Pydantic warning)
        if isinstance(value, list):
            if len(value) == 0:
                log_debug(f"Empty list found for {field_name}, using default: '{default}'")
                return default
            elif len(value) == 1:
                # Single item list, extract the item
                log_debug(f"Single-item list found for {field_name}, extracting: '{value[0]}'")
                return str(value[0]) if value[0] is not None else default
            else:
                # Multiple items, join them
                log_debug(f"Multi-item list found for {field_name}, joining: {value}")
                return " | ".join(str(item) for item in value if item is not None)

        # Handle other unexpected types
        if not isinstance(value, str):
            log_debug(f"Non-string type {type(value)} found for {field_name}, converting: '{value}'")
            try:
                return str(value)
            except Exception as e:
                log_warning(f"Failed to convert {field_name} to string: {e}, using default")
                return default

        # Already a string, return as-is
        return value

    def _content_row_to_content(self, content_row: KnowledgeRow) -> Content:
        """Convert a KnowledgeRow to a Content object."""
        return Content(
            id=content_row.id,
            name=content_row.name,
            description=content_row.description,
            metadata=content_row.metadata,
            file_type=content_row.type,
            size=content_row.size,
            status=ContentStatus(content_row.status) if content_row.status else None,
            status_message=content_row.status_message,
            created_at=content_row.created_at,
            updated_at=content_row.updated_at if content_row.updated_at else content_row.created_at,
            external_id=content_row.external_id,
        )

    def _build_knowledge_row(self, content: Content) -> KnowledgeRow:
        """Build a KnowledgeRow from a Content object."""
        created_at = content.created_at if content.created_at else int(time.time())
        updated_at = content.updated_at if content.updated_at else int(time.time())
        file_type = (
            content.file_type
            if content.file_type
            else content.file_data.type
            if content.file_data and content.file_data.type
            else None
        )
        return KnowledgeRow(
            id=content.id,
            name=self._ensure_string_field(content.name, "content.name", default=""),
            description=self._ensure_string_field(content.description, "content.description", default=""),
            metadata=content.metadata,
            type=file_type,
            size=content.size
            if content.size
            else len(content.file_data.content)
            if content.file_data and content.file_data.content
            else None,
            linked_to=self.name if self.name else "",
            access_count=0,
            status=content.status if content.status else ContentStatus.PROCESSING,
            status_message=self._ensure_string_field(content.status_message, "content.status_message", default=""),
            created_at=created_at,
            updated_at=updated_at,
        )

    def _parse_content_status(self, status_str: Optional[str]) -> ContentStatus:
        """Parse status string to ContentStatus enum."""
        try:
            return ContentStatus(status_str.lower()) if status_str else ContentStatus.PROCESSING
        except ValueError:
            if status_str and "failed" in status_str.lower():
                return ContentStatus.FAILED
            elif status_str and "completed" in status_str.lower():
                return ContentStatus.COMPLETED
            return ContentStatus.PROCESSING
