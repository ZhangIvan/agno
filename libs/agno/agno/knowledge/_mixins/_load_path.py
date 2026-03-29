"""Path loading methods for the Knowledge class."""

import asyncio
from pathlib import Path
from typing import List, Optional, cast

from agno.knowledge.content import Content, ContentStatus
from agno.knowledge.reader import ReaderFactory
from agno.knowledge.types import KnowledgeContentOrigin
from agno.utils.log import log_debug, log_info, log_warning
from agno.utils.string import generate_id


class _KnowledgePathLoaderMixin:
    """Path loading methods extracted from _KnowledgeLoadingMixin."""

    async def _aload_from_path(
        self,
        content: Content,
        upsert: bool,
        skip_if_exists: bool,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
    ):
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)

        log_info(f"Adding content from path, {content.id}, {content.name}, {content.path}, {content.description}")
        path = Path(content.path)  # type: ignore

        is_file = await asyncio.to_thread(path.is_file)
        if is_file:
            if self._should_include_file(str(path), include, exclude):
                log_debug(f"Adding file {path} due to include/exclude filters")

                # Set name from path if not provided
                if not content.name:
                    content.name = path.name

                await self._ainsert_contents_db(content)
                if await self._async_should_skip(content.content_hash, skip_if_exists):  # type: ignore[arg-type]
                    content.status = ContentStatus.COMPLETED
                    await self._aupdate_content(content)
                    return

                # Handle LightRAG special case - read file and upload directly
                if self.vector_db.__class__.__name__ == "LightRag":
                    await self._aprocess_lightrag_content(content, KnowledgeContentOrigin.PATH)
                    return

                if content.reader:
                    reader = content.reader
                else:
                    reader = ReaderFactory.get_reader_for_extension(path.suffix)
                    log_debug(f"Using Reader: {reader.__class__.__name__}")

                if reader:
                    password = content.auth.password if content.auth and content.auth.password is not None else None
                    read_documents = await self._aread(reader, path, name=content.name or path.name, password=password)
                else:
                    read_documents = []

                if not content.file_type:
                    content.file_type = path.suffix

                if not content.size and content.file_data:
                    content.size = len(content.file_data.content)  # type: ignore
                if not content.size:
                    try:
                        stat_result = await asyncio.to_thread(path.stat)
                        content.size = stat_result.st_size
                    except (OSError, IOError) as e:
                        log_warning(f"Could not get file size for {path}: {e}")
                        content.size = 0

                if not content.id:
                    content.id = generate_id(content.content_hash or "")
                self._prepare_documents_for_insert(read_documents, content.id, metadata=content.metadata)

                await self._ahandle_vector_db_insert(content, read_documents, upsert, file_source=path)

        else:
            is_dir = await asyncio.to_thread(path.is_dir)
            if is_dir:
                dir_entries = await asyncio.to_thread(lambda p: list(p.iterdir()), path)
                for file_path in dir_entries:
                    # Apply include/exclude filtering
                    if not self._should_include_file(str(file_path), include, exclude):
                        log_debug(f"Skipping file {file_path} due to include/exclude filters")
                        continue

                    file_content = Content(
                        name=content.name,
                        path=str(file_path),
                        metadata=content.metadata,
                        description=content.description,
                        reader=content.reader,
                    )
                    file_content.content_hash = self._build_content_hash(file_content)
                    file_content.id = generate_id(file_content.content_hash)

                    await self._aload_from_path(file_content, upsert, skip_if_exists, include, exclude)
            else:
                log_warning(f"Invalid path: {path}")

    def _load_from_path(
        self,
        content: Content,
        upsert: bool,
        skip_if_exists: bool,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
    ):
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)

        log_info(f"Adding content from path, {content.id}, {content.name}, {content.path}, {content.description}")
        path = Path(content.path)  # type: ignore

        if path.is_file():
            if self._should_include_file(str(path), include, exclude):
                log_debug(f"Adding file {path} due to include/exclude filters")

                # Set name from path if not provided
                if not content.name:
                    content.name = path.name

                self._insert_contents_db(content)
                if self._should_skip(content.content_hash, skip_if_exists):  # type: ignore[arg-type]
                    content.status = ContentStatus.COMPLETED
                    self._update_content(content)
                    return

                # Handle LightRAG special case - read file and upload directly
                if self.vector_db.__class__.__name__ == "LightRag":
                    self._process_lightrag_content(content, KnowledgeContentOrigin.PATH)
                    return

                if content.reader:
                    reader = content.reader
                else:
                    reader = ReaderFactory.get_reader_for_extension(path.suffix)
                    log_debug(f"Using Reader: {reader.__class__.__name__}")

                if reader:
                    password = content.auth.password if content.auth and content.auth.password is not None else None
                    read_documents = self._read(reader, path, name=content.name or path.name, password=password)
                else:
                    read_documents = []

                if not content.file_type:
                    content.file_type = path.suffix

                if not content.size and content.file_data:
                    content.size = len(content.file_data.content)  # type: ignore
                if not content.size:
                    try:
                        content.size = path.stat().st_size
                    except (OSError, IOError) as e:
                        log_warning(f"Could not get file size for {path}: {e}")
                        content.size = 0

                if not content.id:
                    content.id = generate_id(content.content_hash or "")
                self._prepare_documents_for_insert(read_documents, content.id, metadata=content.metadata)

                self._handle_vector_db_insert(content, read_documents, upsert, file_source=path)

        elif path.is_dir():
            for file_path in path.iterdir():
                # Apply include/exclude filtering
                if not self._should_include_file(str(file_path), include, exclude):
                    log_debug(f"Skipping file {file_path} due to include/exclude filters")
                    continue

                file_content = Content(
                    name=content.name,
                    path=str(file_path),
                    metadata=content.metadata,
                    description=content.description,
                    reader=content.reader,
                )
                file_content.content_hash = self._build_content_hash(file_content)
                file_content.id = generate_id(file_content.content_hash)

                self._load_from_path(file_content, upsert, skip_if_exists, include, exclude)
        else:
            log_warning(f"Invalid path: {path}")
