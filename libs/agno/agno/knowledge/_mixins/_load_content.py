"""Raw content (text/bytes) loading methods for the Knowledge class."""

import io
from pathlib import Path
from typing import cast

from agno.knowledge.content import Content, ContentStatus, FileData
from agno.knowledge.types import KnowledgeContentOrigin
from agno.utils.log import log_debug, log_info
from agno.utils.string import generate_id


class _KnowledgeContentLoaderMixin:
    """Methods for loading raw content (text/bytes) into the Knowledge base."""

    async def _aload_from_content(
        self,
        content: Content,
        upsert: bool = True,
        skip_if_exists: bool = False,
    ):
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)

        if content.name:
            name = content.name
        elif content.file_data and content.file_data.filename:
            name = content.file_data.filename
        elif content.file_data and content.file_data.content:
            if isinstance(content.file_data.content, bytes):
                name = content.file_data.content[:10].decode("utf-8", errors="ignore")
            elif isinstance(content.file_data.content, str):
                name = (
                    content.file_data.content[:10]
                    if len(content.file_data.content) >= 10
                    else content.file_data.content
                )
            else:
                name = str(content.file_data.content)[:10]
        else:
            name = None

        if name is not None:
            content.name = name

        log_info(f"Adding content from {content.name}")

        await self._ainsert_contents_db(content)
        if await self._async_should_skip(content.content_hash, skip_if_exists):  # type: ignore[arg-type]
            content.status = ContentStatus.COMPLETED
            await self._aupdate_content(content)
            return

        if content.file_data and self.vector_db.__class__.__name__ == "LightRag":
            await self._aprocess_lightrag_content(content, KnowledgeContentOrigin.CONTENT)
            return

        read_documents = []

        if isinstance(content.file_data, str):
            content_bytes = content.file_data.encode("utf-8", errors="replace")
            content_io = io.BytesIO(content_bytes)

            if content.reader:
                log_debug(f"Using reader: {content.reader.__class__.__name__} to read content")
                read_documents = await content.reader.async_read(content_io, name=name)
            else:
                text_reader = self.text_reader
                if text_reader:
                    read_documents = await text_reader.async_read(content_io, name=name)
                else:
                    content.status = ContentStatus.FAILED
                    content.status_message = "Text reader not available"
                    await self._aupdate_content(content)
                    return

        elif isinstance(content.file_data, FileData):
            if content.file_data.type:
                if isinstance(content.file_data.content, bytes):
                    content_io = io.BytesIO(content.file_data.content)
                elif isinstance(content.file_data.content, str):
                    content_bytes = content.file_data.content.encode("utf-8", errors="replace")
                    content_io = io.BytesIO(content_bytes)
                else:
                    content_io = content.file_data.content  # type: ignore

                # Respect an explicitly provided reader; otherwise select based on file type
                # (browsers often send wrong MIME types for Excel files)
                if content.reader:
                    log_debug(f"Using reader: {content.reader.__class__.__name__} to read content")
                    reader = content.reader
                else:
                    # Prefer filename extension over MIME type for reader selection
                    # (browsers often send wrong MIME types for Excel files)
                    reader_hint = content.file_data.type
                    if content.file_data.filename:
                        ext = Path(content.file_data.filename).suffix.lower()
                        if ext:
                            reader_hint = ext
                    reader = self._select_reader(reader_hint)
                # Use file_data.filename for reader (preserves extension for format detection)
                reader_name = content.file_data.filename or content.name or f"content_{content.file_data.type}"
                read_documents = await reader.async_read(content_io, name=reader_name)
                if not content.id:
                    content.id = generate_id(content.content_hash or "")
                self._prepare_documents_for_insert(read_documents, content.id, metadata=content.metadata)
                if len(read_documents) == 0:
                    content.status = ContentStatus.FAILED
                    content.status_message = "Content could not be read"
                    await self._aupdate_content(content)
                    return

        else:
            content.status = ContentStatus.FAILED
            content.status_message = "No content provided"
            await self._aupdate_content(content)
            return

        await self._ahandle_vector_db_insert(content, read_documents, upsert, file_source=content_io)

    def _load_from_content(
        self,
        content: Content,
        upsert: bool = True,
        skip_if_exists: bool = False,
    ):
        """Synchronous version of _load_from_content."""
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)

        if content.name:
            name = content.name
        elif content.file_data and content.file_data.filename:
            name = content.file_data.filename
        elif content.file_data and content.file_data.content:
            if isinstance(content.file_data.content, bytes):
                name = content.file_data.content[:10].decode("utf-8", errors="ignore")
            elif isinstance(content.file_data.content, str):
                name = (
                    content.file_data.content[:10]
                    if len(content.file_data.content) >= 10
                    else content.file_data.content
                )
            else:
                name = str(content.file_data.content)[:10]
        else:
            name = None

        if name is not None:
            content.name = name

        log_info(f"Adding content from {content.name}")

        self._insert_contents_db(content)
        if self._should_skip(content.content_hash, skip_if_exists):  # type: ignore[arg-type]
            content.status = ContentStatus.COMPLETED
            self._update_content(content)
            return

        if content.file_data and self.vector_db.__class__.__name__ == "LightRag":
            self._process_lightrag_content(content, KnowledgeContentOrigin.CONTENT)
            return

        read_documents = []

        if isinstance(content.file_data, str):
            content_bytes = content.file_data.encode("utf-8", errors="replace")
            content_io = io.BytesIO(content_bytes)

            if content.reader:
                log_debug(f"Using reader: {content.reader.__class__.__name__} to read content")
                read_documents = content.reader.read(content_io, name=name)
            else:
                text_reader = self.text_reader
                if text_reader:
                    read_documents = text_reader.read(content_io, name=name)
                else:
                    content.status = ContentStatus.FAILED
                    content.status_message = "Text reader not available"
                    self._update_content(content)
                    return

        elif isinstance(content.file_data, FileData):
            if content.file_data.type:
                if isinstance(content.file_data.content, bytes):
                    content_io = io.BytesIO(content.file_data.content)
                elif isinstance(content.file_data.content, str):
                    content_bytes = content.file_data.content.encode("utf-8", errors="replace")
                    content_io = io.BytesIO(content_bytes)
                else:
                    content_io = content.file_data.content  # type: ignore

                # Respect an explicitly provided reader; otherwise select based on file type
                if content.reader:
                    log_debug(f"Using reader: {content.reader.__class__.__name__} to read content")
                    reader = content.reader
                else:
                    # Prefer filename extension over MIME type for reader selection
                    # (browsers often send wrong MIME types for Excel files)
                    reader_hint = content.file_data.type
                    if content.file_data.filename:
                        ext = Path(content.file_data.filename).suffix.lower()
                        if ext:
                            reader_hint = ext
                    reader = self._select_reader(reader_hint)
                # Use file_data.filename for reader (preserves extension for format detection)
                reader_name = content.file_data.filename or content.name or f"content_{content.file_data.type}"
                read_documents = reader.read(content_io, name=reader_name)
                if not content.id:
                    content.id = generate_id(content.content_hash or "")
                self._prepare_documents_for_insert(read_documents, content.id, metadata=content.metadata)
                if len(read_documents) == 0:
                    content.status = ContentStatus.FAILED
                    content.status_message = "Content could not be read"
                    self._update_content(content)
                    return

        else:
            content.status = ContentStatus.FAILED
            content.status_message = "No content provided"
            self._update_content(content)
            return

        self._handle_vector_db_insert(content, read_documents, upsert, file_source=content_io)
