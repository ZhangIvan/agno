"""Reader management methods for the Knowledge class.

Handles reader lifecycle: construction, lazy-loading via factory,
include/exclude pattern matching, and MIME type detection.
"""

import os
from typing import Dict, List, Optional

from agno.knowledge.reader import Reader, ReaderFactory
from agno.utils.log import log_info, log_warning


class _KnowledgeReaderMixin:
    """Reader lifecycle and selection methods extracted from Knowledge."""

    def construct_readers(self):
        """Initialize readers dictionary for lazy loading."""
        if self.readers is None:
            self.readers = {}

    def add_reader(self, reader: Reader):
        """Add a custom reader to the knowledge base."""
        if self.readers is None:
            self.readers = {}

        reader_key = self._generate_reader_key(reader)
        self.readers[reader_key] = reader
        return reader

    def get_readers(self) -> Dict[str, Reader]:
        """Get all currently loaded readers (only returns readers that have been used)."""
        if self.readers is None:
            self.readers = {}
        elif not isinstance(self.readers, dict):
            # Defensive check: if readers is not a dict (e.g., was set to a list), convert it
            if isinstance(self.readers, list):
                readers_dict: Dict[str, Reader] = {}
                for reader in self.readers:
                    if isinstance(reader, Reader):
                        reader_key = self._generate_reader_key(reader)
                        original_key = reader_key
                        counter = 1
                        while reader_key in readers_dict:
                            reader_key = f"{original_key}_{counter}"
                            counter += 1
                        readers_dict[reader_key] = reader
                self.readers = readers_dict
            else:
                self.readers = {}

        return self.readers

    # --- Reader Helper Methods ---

    def _generate_reader_key(self, reader: Reader) -> str:
        """Generate a key for a reader instance."""
        if reader.name:
            return f"{reader.name.lower().replace(' ', '_')}"
        else:
            return f"{reader.__class__.__name__.lower().replace(' ', '_')}"

    def _get_reader(self, reader_type: str) -> Optional[Reader]:
        """Get a cached reader or create it if not cached, handling missing dependencies gracefully."""
        if self.readers is None:
            self.readers = {}

        if reader_type not in self.readers:
            try:
                reader = ReaderFactory.create_reader(reader_type)
                if reader:
                    self.readers[reader_type] = reader
                else:
                    return None

            except Exception as e:
                log_warning(f"Cannot create {reader_type} reader {e}")
                return None

        return self.readers.get(reader_type)

    def _select_reader(self, extension: str) -> Reader:
        """Select the appropriate reader for a file extension."""
        log_info(f"Selecting reader for extension: {extension}")
        return ReaderFactory.get_reader_for_extension(extension)

    def _should_include_file(self, file_path: str, include: Optional[List[str]], exclude: Optional[List[str]]) -> bool:
        """
        Determine if a file should be included based on include/exclude patterns.

        Logic:
        1. If include is specified, file must match at least one include pattern
        2. If exclude is specified, file must not match any exclude pattern
        3. If neither specified, include all files
        """
        import fnmatch

        file_name = os.path.basename(file_path)

        def _matches(path: str, name: str, pattern: str) -> bool:
            return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(name, pattern)

        # If include patterns specified, file must match at least one
        if include:
            if not any(_matches(file_path, file_name, pattern) for pattern in include):
                return False

        # If exclude patterns specified, file must not match any
        if exclude:
            if any(_matches(file_path, file_name, pattern) for pattern in exclude):
                return False

        return True

    def _is_text_mime_type(self, mime_type: str) -> bool:
        """Check if a MIME type represents text content that can be safely encoded as UTF-8."""
        if not mime_type:
            return False

        text_types = [
            "text/",
            "application/json",
            "application/xml",
            "application/javascript",
            "application/csv",
            "application/sql",
        ]

        return any(mime_type.startswith(t) for t in text_types)

    # --- Reader Properties (Lazy Loading) ---

    @property
    def pdf_reader(self) -> Optional[Reader]:
        return self._get_reader("pdf")

    @property
    def csv_reader(self) -> Optional[Reader]:
        return self._get_reader("csv")

    @property
    def excel_reader(self) -> Optional[Reader]:
        return self._get_reader("excel")

    @property
    def docx_reader(self) -> Optional[Reader]:
        return self._get_reader("docx")

    @property
    def pptx_reader(self) -> Optional[Reader]:
        return self._get_reader("pptx")

    @property
    def json_reader(self) -> Optional[Reader]:
        return self._get_reader("json")

    @property
    def markdown_reader(self) -> Optional[Reader]:
        return self._get_reader("markdown")

    @property
    def text_reader(self) -> Optional[Reader]:
        return self._get_reader("text")

    @property
    def image_reader(self) -> Optional[Reader]:
        return self._get_reader("image")

    @property
    def website_reader(self) -> Optional[Reader]:
        return self._get_reader("website")

    @property
    def firecrawl_reader(self) -> Optional[Reader]:
        return self._get_reader("firecrawl")

    @property
    def youtube_reader(self) -> Optional[Reader]:
        return self._get_reader("youtube")
