"""URL loading methods for the Knowledge class."""

import asyncio
import os
import tempfile
from os.path import basename
from pathlib import Path
from typing import Dict, List, Optional, cast
from urllib.parse import urlparse

import httpx
from httpx import AsyncClient

from agno.knowledge.content import Content, ContentStatus
from agno.knowledge.document import Document
from agno.knowledge.types import KnowledgeContentOrigin
from agno.knowledge.utils import set_agno_metadata
from agno.utils.log import log_debug, log_error, log_info, log_warning
from agno.utils.string import generate_id


class _KnowledgeUrlLoaderMixin:
    """URL loading methods: _aload_from_url, _load_from_url."""

    async def _aload_from_url(
        self,
        content: Content,
        upsert: bool,
        skip_if_exists: bool,
    ):
        """Load the content in the contextual URL

        1. Set content hash
        2. Validate the URL
        3. Read the content
        4. Prepare and insert the content in the vector database
        """
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)

        log_info(f"Adding content from URL {content.url}")
        content.file_type = "url"

        if not content.url:
            raise ValueError("No url provided")

        # Store URL source metadata in _agno for source tracking
        content.metadata = set_agno_metadata(content.metadata, "source_type", "url")
        content.metadata = set_agno_metadata(content.metadata, "source_url", content.url)

        # Set name from URL if not provided
        if not content.name and content.url:
            parsed = urlparse(content.url)
            url_path = Path(parsed.path)
            content.name = url_path.name if url_path.name else content.url

        # 1. Add content to contents database
        await self._ainsert_contents_db(content)
        if await self._async_should_skip(content.content_hash, skip_if_exists):  # type: ignore[arg-type]
            content.status = ContentStatus.COMPLETED
            await self._aupdate_content(content)
            return

        if self.vector_db.__class__.__name__ == "LightRag":
            await self._aprocess_lightrag_content(content, KnowledgeContentOrigin.URL)
            return

        # 2. Validate URL
        try:
            parsed_url = urlparse(content.url)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                content.status = ContentStatus.FAILED
                content.status_message = f"Invalid URL format: {content.url}"
                await self._aupdate_content(content)
                log_warning(f"Invalid URL format: {content.url}")
                return
        except Exception as e:
            content.status = ContentStatus.FAILED
            content.status_message = f"Invalid URL: {content.url} - {str(e)}"
            await self._aupdate_content(content)
            log_warning(f"Invalid URL: {content.url} - {str(e)}")
            return
        # 3. Fetch and load content if file has an extension
        url_path = Path(parsed_url.path)
        file_extension = url_path.suffix.lower()

        # If URL has no extension, try to detect from Content-Type via HEAD request
        if not file_extension:
            file_extension = await self._async_detect_extension_from_content_type(content.url) or ""

        # Download to a temp file on disk instead of BytesIO (memory) so that
        # large files don't exhaust memory.  The temp file is cleaned up at the
        # end of this method.
        temp_file_path: Optional[Path] = None
        if file_extension:
            # Stream download directly to disk to avoid loading entire file into memory
            async with AsyncClient(follow_redirects=True) as client:
                async with client.stream("GET", content.url) as response:
                    response.raise_for_status()
                    with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as tmp:
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            tmp.write(chunk)
                        temp_file_path = Path(tmp.name)

        # 4. Select reader
        name = content.name if content.name else content.url
        if file_extension:
            reader, default_name = self._select_reader_by_extension(file_extension, content.reader)
            if default_name and file_extension == ".csv":
                name = basename(parsed_url.path) or default_name
        else:
            reader = content.reader or self.website_reader
        # 5. Read content
        try:
            read_documents = []
            if reader is not None:
                # Special handling for YouTubeReader
                if reader.__class__.__name__ == "YouTubeReader":
                    read_documents = await reader.async_read(content.url, name=name)
                else:
                    password = content.auth.password if content.auth and content.auth.password is not None else None
                    source = temp_file_path if temp_file_path else content.url
                    read_documents = await self._aread(reader, source, name=name, password=password)

        except Exception as e:
            # Clean up temp file on read failure
            if temp_file_path:
                try:
                    await asyncio.to_thread(os.unlink, temp_file_path)
                except OSError:
                    pass
            log_error(f"Error reading URL: {content.url} - {str(e)}")
            content.status = ContentStatus.FAILED
            content.status_message = f"Error reading URL: {content.url} - {str(e)}"
            await self._aupdate_content(content)
            return

        # 6. Chunk documents if needed
        if reader and not reader.chunk:
            read_documents = await reader.chunk_documents_async(read_documents)

        # 7. Group documents by source URL for multi-page readers (like WebsiteReader)
        docs_by_source: Dict[str, List[Document]] = {}
        for doc in read_documents:
            source_url = doc.meta_data.get("url", content.url) if doc.meta_data else content.url
            source_url = source_url or "unknown"
            if source_url not in docs_by_source:
                docs_by_source[source_url] = []
            docs_by_source[source_url].append(doc)

        # 8. Process each source separately if multiple sources exist
        if len(docs_by_source) > 1:
            for source_url, source_docs in docs_by_source.items():
                # Compute per-document hash based on actual source URL
                doc_hash = self._build_document_content_hash(source_docs[0], content)

                # Check skip_if_exists for each source individually
                if await self._async_should_skip(doc_hash, skip_if_exists):
                    log_debug(f"Skipping already indexed: {source_url}")
                    continue

                doc_id = generate_id(doc_hash)
                self._prepare_documents_for_insert(source_docs, doc_id, calculate_sizes=True)

                # Upload page images for this source group
                local_page_paths: List[str] = []
                if self.page_image_storage:
                    source_docs, local_page_paths = await self._async_upload_page_images(source_docs)

                # Insert with per-document hash
                if self.vector_db.upsert_available() and upsert:
                    try:
                        await self.vector_db.async_upsert(doc_hash, source_docs, content.metadata)
                    except Exception as e:
                        log_error(f"Error upserting document from {source_url}: {e}")
                        if local_page_paths:
                            await self._async_cleanup_local_page_images(source_docs, local_page_paths)
                        continue
                else:
                    try:
                        await self.vector_db.async_insert(doc_hash, documents=source_docs, filters=content.metadata)
                    except Exception as e:
                        log_error(f"Error inserting document from {source_url}: {e}")
                        if local_page_paths:
                            await self._async_cleanup_local_page_images(source_docs, local_page_paths)
                        continue

                # Cleanup temp files after successful insert
                if local_page_paths:
                    await self._async_cleanup_local_page_images(source_docs, local_page_paths)

            # Clean up temp file after multi-source processing
            if temp_file_path:
                try:
                    await asyncio.to_thread(os.unlink, temp_file_path)
                except OSError:
                    pass

            content.status = ContentStatus.COMPLETED
            await self._aupdate_content(content)
            return

        # 9. Single source - use existing logic with original content hash
        if not content.id:
            content.id = generate_id(content.content_hash or "")
        self._prepare_documents_for_insert(read_documents, content.id, calculate_sizes=True)
        try:
            await self._ahandle_vector_db_insert(content, read_documents, upsert, file_source=temp_file_path)
        finally:
            # Clean up temp file after all processing is done (guaranteed even on exception)
            if temp_file_path:
                try:
                    await asyncio.to_thread(os.unlink, temp_file_path)
                except OSError:
                    pass

    def _load_from_url(
        self,
        content: Content,
        upsert: bool,
        skip_if_exists: bool,
    ):
        """Synchronous version of _load_from_url.

        Load the content from a URL:
        1. Set content hash
        2. Validate the URL
        3. Read the content
        4. Prepare and insert the content in the vector database
        """
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)

        log_info(f"Adding content from URL {content.url}")
        content.file_type = "url"

        if not content.url:
            raise ValueError("No url provided")

        # Store URL source metadata in _agno for source tracking
        content.metadata = set_agno_metadata(content.metadata, "source_type", "url")
        content.metadata = set_agno_metadata(content.metadata, "source_url", content.url)

        # Set name from URL if not provided
        if not content.name and content.url:
            parsed = urlparse(content.url)
            url_path = Path(parsed.path)
            content.name = url_path.name if url_path.name else content.url

        # 1. Add content to contents database
        self._insert_contents_db(content)
        if self._should_skip(content.content_hash, skip_if_exists):  # type: ignore[arg-type]
            content.status = ContentStatus.COMPLETED
            self._update_content(content)
            return

        if self.vector_db.__class__.__name__ == "LightRag":
            self._process_lightrag_content(content, KnowledgeContentOrigin.URL)
            return

        # 2. Validate URL
        try:
            parsed_url = urlparse(content.url)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                content.status = ContentStatus.FAILED
                content.status_message = f"Invalid URL format: {content.url}"
                self._update_content(content)
                log_warning(f"Invalid URL format: {content.url}")
                return
        except Exception as e:
            content.status = ContentStatus.FAILED
            content.status_message = f"Invalid URL: {content.url} - {str(e)}"
            self._update_content(content)
            log_warning(f"Invalid URL: {content.url} - {str(e)}")
            return

        # 3. Fetch and load content if file has an extension
        url_path = Path(parsed_url.path)
        file_extension = url_path.suffix.lower()

        # If URL has no extension, try to detect from Content-Type via HEAD request
        if not file_extension:
            file_extension = self._detect_extension_from_content_type(content.url) or ""

        # Stream download directly to disk to avoid loading entire file into memory.
        temp_file_path: Optional[Path] = None
        if file_extension:
            with httpx.stream("GET", content.url, follow_redirects=True) as stream:
                stream.raise_for_status()
                with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as tmp:
                    for chunk in stream.iter_bytes(chunk_size=65536):
                        tmp.write(chunk)
                    temp_file_path = Path(tmp.name)

        # 4. Select reader
        name = content.name if content.name else content.url
        if file_extension:
            reader, default_name = self._select_reader_by_extension(file_extension, content.reader)
            if default_name and file_extension == ".csv":
                name = basename(parsed_url.path) or default_name
        else:
            reader = content.reader or self.website_reader

        # 5. Read content
        try:
            read_documents = []
            if reader is not None:
                # Special handling for YouTubeReader
                if reader.__class__.__name__ == "YouTubeReader":
                    read_documents = reader.read(content.url, name=name)
                else:
                    password = content.auth.password if content.auth and content.auth.password is not None else None
                    source = temp_file_path if temp_file_path else content.url
                    read_documents = self._read(reader, source, name=name, password=password)

        except Exception as e:
            # Clean up temp file on read failure
            if temp_file_path:
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass
            log_error(f"Error reading URL: {content.url} - {str(e)}")
            content.status = ContentStatus.FAILED
            content.status_message = f"Error reading URL: {content.url} - {str(e)}"
            self._update_content(content)
            return

        # 6. Chunk documents if needed (sync version)
        if reader:
            read_documents = self._chunk_documents_sync(reader, read_documents)

        # 7. Group documents by source URL for multi-page readers (like WebsiteReader)
        docs_by_source: Dict[str, List[Document]] = {}
        for doc in read_documents:
            source_url = doc.meta_data.get("url", content.url) if doc.meta_data else content.url
            source_url = source_url or "unknown"
            if source_url not in docs_by_source:
                docs_by_source[source_url] = []
            docs_by_source[source_url].append(doc)

        # 8. Process each source separately if multiple sources exist
        if len(docs_by_source) > 1:
            for source_url, source_docs in docs_by_source.items():
                # Compute per-document hash based on actual source URL
                doc_hash = self._build_document_content_hash(source_docs[0], content)

                # Check skip_if_exists for each source individually
                if self._should_skip(doc_hash, skip_if_exists):
                    log_debug(f"Skipping already indexed: {source_url}")
                    continue

                doc_id = generate_id(doc_hash)
                self._prepare_documents_for_insert(source_docs, doc_id, calculate_sizes=True)

                # Upload page images for this source group
                local_page_paths: List[str] = []
                if self.page_image_storage:
                    source_docs, local_page_paths = self._upload_page_images(source_docs)

                # Insert with per-document hash
                if self.vector_db.upsert_available() and upsert:
                    try:
                        self.vector_db.upsert(doc_hash, source_docs, content.metadata)
                    except Exception as e:
                        log_error(f"Error upserting document from {source_url}: {e}")
                        if local_page_paths:
                            self._cleanup_local_page_images(source_docs, local_page_paths)
                        continue
                else:
                    try:
                        self.vector_db.insert(doc_hash, documents=source_docs, filters=content.metadata)
                    except Exception as e:
                        log_error(f"Error inserting document from {source_url}: {e}")
                        if local_page_paths:
                            self._cleanup_local_page_images(source_docs, local_page_paths)
                        continue

                # Cleanup temp files after successful insert
                if local_page_paths:
                    self._cleanup_local_page_images(source_docs, local_page_paths)

            # Clean up temp file after multi-source processing
            if temp_file_path:
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass

            content.status = ContentStatus.COMPLETED
            self._update_content(content)
            return

        # 9. Single source - use existing logic with original content hash
        if not content.id:
            content.id = generate_id(content.content_hash or "")
        self._prepare_documents_for_insert(read_documents, content.id, calculate_sizes=True)
        try:
            self._handle_vector_db_insert(content, read_documents, upsert, file_source=temp_file_path)
        finally:
            # Clean up temp file after all processing is done (guaranteed even on exception)
            if temp_file_path:
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass
