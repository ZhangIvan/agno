"""LightRAG processing methods for the Knowledge class.

These methods handle special processing paths when the vector database
is a LightRAG instance, which has its own file/text insertion APIs.
"""

import asyncio
from pathlib import Path
from typing import cast

from agno.knowledge.content import Content, ContentStatus
from agno.knowledge.types import KnowledgeContentOrigin
from agno.utils.log import log_error, log_info, log_warning
from agno.utils.string import generate_id


class _KnowledgeLightRAGMixin:
    """LightRAG-specific processing extracted from Knowledge."""

    async def _aprocess_lightrag_content(self, content: Content, content_type: KnowledgeContentOrigin) -> None:
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)

        await self._ainsert_contents_db(content)
        if content_type == KnowledgeContentOrigin.PATH:
            if content.file_data is None:
                log_warning("No file data provided")

            if content.path is None:
                log_error("No path provided for content")
                return

            path = Path(content.path)

            log_info(f"Uploading file to LightRAG from path: {path}")
            try:
                # Read the file content from path (non-blocking)
                file_content = await asyncio.to_thread(path.read_bytes)

                # Get file type from extension or content.file_type
                file_type = content.file_type or path.suffix

                if self.vector_db and hasattr(self.vector_db, "insert_file_bytes"):
                    result = await self.vector_db.insert_file_bytes(
                        file_content=file_content,
                        filename=path.name,  # Use the original filename with extension
                        content_type=file_type,
                        send_metadata=True,  # Enable metadata so server knows the file type
                    )

                else:
                    log_error("Vector database does not support file insertion")
                    content.status = ContentStatus.FAILED
                    await self._aupdate_content(content)
                    return
                content.external_id = result
                content.status = ContentStatus.COMPLETED
                await self._aupdate_content(content)
                return

            except Exception as e:
                log_error(f"Error uploading file to LightRAG: {e}")
                content.status = ContentStatus.FAILED
                content.status_message = f"Could not upload to LightRAG: {str(e)}"
                await self._aupdate_content(content)
                return

        elif content_type == KnowledgeContentOrigin.URL:
            log_info(f"Uploading file to LightRAG from URL: {content.url}")
            try:
                reader = content.reader or self.website_reader
                if reader is None:
                    log_error("No URL reader available")
                    content.status = ContentStatus.FAILED
                    await self._aupdate_content(content)
                    return

                reader.chunk = False
                read_documents = await reader.async_read(content.url, name=content.name)
                if not content.id:
                    content.id = generate_id(content.content_hash or "")
                self._prepare_documents_for_insert(read_documents, content.id)

                if not read_documents:
                    log_error("No documents read from URL")
                    content.status = ContentStatus.FAILED
                    await self._aupdate_content(content)
                    return

                if self.vector_db and hasattr(self.vector_db, "insert_text"):
                    result = await self.vector_db.insert_text(
                        file_source=content.url,
                        text=read_documents[0].content,
                    )
                else:
                    log_error("Vector database does not support text insertion")
                    content.status = ContentStatus.FAILED
                    await self._aupdate_content(content)
                    return

                content.external_id = result
                content.status = ContentStatus.COMPLETED
                await self._aupdate_content(content)
                return

            except Exception as e:
                log_error(f"Error uploading file to LightRAG: {e}")
                content.status = ContentStatus.FAILED
                content.status_message = f"Could not upload to LightRAG: {str(e)}"
                await self._aupdate_content(content)
                return

        elif content_type == KnowledgeContentOrigin.CONTENT:
            filename = (
                content.file_data.filename if content.file_data and content.file_data.filename else "uploaded_file"
            )
            log_info(f"Uploading file to LightRAG: {filename}")

            # Use the content from file_data
            if content.file_data and content.file_data.content:
                if self.vector_db and hasattr(self.vector_db, "insert_file_bytes"):
                    result = await self.vector_db.insert_file_bytes(
                        file_content=content.file_data.content,
                        filename=filename,
                        content_type=content.file_data.type,
                        send_metadata=True,  # Enable metadata so server knows the file type
                    )
                else:
                    log_error("Vector database does not support file insertion")
                    content.status = ContentStatus.FAILED
                    await self._aupdate_content(content)
                    return
                content.external_id = result
                content.status = ContentStatus.COMPLETED
                await self._aupdate_content(content)
            else:
                log_warning(f"No file data available for LightRAG upload: {content.name}")
            return

        elif content_type == KnowledgeContentOrigin.TOPIC:
            log_info(f"Uploading file to LightRAG: {content.name}")

            if content.reader is None:
                log_error("No reader available for topic content")
                content.status = ContentStatus.FAILED
                await self._aupdate_content(content)
                return

            if not content.topics:
                log_error("No topics available for content")
                content.status = ContentStatus.FAILED
                await self._aupdate_content(content)
                return

            read_documents = await content.reader.async_read(content.topics)
            if len(read_documents) > 0:
                if self.vector_db and hasattr(self.vector_db, "insert_text"):
                    result = await self.vector_db.insert_text(
                        file_source=content.topics[0],
                        text=read_documents[0].content,
                    )
                else:
                    log_error("Vector database does not support text insertion")
                    content.status = ContentStatus.FAILED
                    await self._aupdate_content(content)
                    return
                content.external_id = result
                content.status = ContentStatus.COMPLETED
                await self._aupdate_content(content)
                return
            else:
                log_warning(f"No documents found for LightRAG upload: {content.name}")
                return

    def _process_lightrag_content(self, content: Content, content_type: KnowledgeContentOrigin) -> None:
        """Synchronously process LightRAG content. Uses asyncio.run() only for LightRAG-specific async methods."""
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)

        self._insert_contents_db(content)
        if content_type == KnowledgeContentOrigin.PATH:
            if content.file_data is None:
                log_warning("No file data provided")

            if content.path is None:
                log_error("No path provided for content")
                return

            path = Path(content.path)

            log_info(f"Uploading file to LightRAG from path: {path}")
            try:
                # Read the file content from path
                with open(path, "rb") as f:
                    file_content = f.read()

                # Get file type from extension or content.file_type
                file_type = content.file_type or path.suffix

                if self.vector_db and hasattr(self.vector_db, "insert_file_bytes"):
                    # LightRAG only has async methods, use asyncio.run() here
                    result = asyncio.run(
                        self.vector_db.insert_file_bytes(
                            file_content=file_content,
                            filename=path.name,
                            content_type=file_type,
                            send_metadata=True,
                        )
                    )
                else:
                    log_error("Vector database does not support file insertion")
                    content.status = ContentStatus.FAILED
                    self._update_content(content)
                    return
                content.external_id = result
                content.status = ContentStatus.COMPLETED
                self._update_content(content)
                return

            except Exception as e:
                log_error(f"Error uploading file to LightRAG: {e}")
                content.status = ContentStatus.FAILED
                content.status_message = f"Could not upload to LightRAG: {str(e)}"
                self._update_content(content)
                return

        elif content_type == KnowledgeContentOrigin.URL:
            log_info(f"Uploading file to LightRAG from URL: {content.url}")
            try:
                reader = content.reader or self.website_reader
                if reader is None:
                    log_error("No URL reader available")
                    content.status = ContentStatus.FAILED
                    self._update_content(content)
                    return

                reader.chunk = False
                read_documents = reader.read(content.url, name=content.name)
                if not content.id:
                    content.id = generate_id(content.content_hash or "")
                self._prepare_documents_for_insert(read_documents, content.id)

                if not read_documents:
                    log_error("No documents read from URL")
                    content.status = ContentStatus.FAILED
                    self._update_content(content)
                    return

                if self.vector_db and hasattr(self.vector_db, "insert_text"):
                    # LightRAG only has async methods, use asyncio.run() here
                    result = asyncio.run(
                        self.vector_db.insert_text(
                            file_source=content.url,
                            text=read_documents[0].content,
                        )
                    )
                else:
                    log_error("Vector database does not support text insertion")
                    content.status = ContentStatus.FAILED
                    self._update_content(content)
                    return

                content.external_id = result
                content.status = ContentStatus.COMPLETED
                self._update_content(content)
                return

            except Exception as e:
                log_error(f"Error uploading file to LightRAG: {e}")
                content.status = ContentStatus.FAILED
                content.status_message = f"Could not upload to LightRAG: {str(e)}"
                self._update_content(content)
                return

        elif content_type == KnowledgeContentOrigin.CONTENT:
            filename = (
                content.file_data.filename if content.file_data and content.file_data.filename else "uploaded_file"
            )
            log_info(f"Uploading file to LightRAG: {filename}")

            # Use the content from file_data
            if content.file_data and content.file_data.content:
                if self.vector_db and hasattr(self.vector_db, "insert_file_bytes"):
                    # LightRAG only has async methods, use asyncio.run() here
                    result = asyncio.run(
                        self.vector_db.insert_file_bytes(
                            file_content=content.file_data.content,
                            filename=filename,
                            content_type=content.file_data.type,
                            send_metadata=True,
                        )
                    )
                else:
                    log_error("Vector database does not support file insertion")
                    content.status = ContentStatus.FAILED
                    self._update_content(content)
                    return
                content.external_id = result
                content.status = ContentStatus.COMPLETED
                self._update_content(content)
            else:
                log_warning(f"No file data available for LightRAG upload: {content.name}")
            return

        elif content_type == KnowledgeContentOrigin.TOPIC:
            log_info(f"Uploading file to LightRAG: {content.name}")

            if content.reader is None:
                log_error("No reader available for topic content")
                content.status = ContentStatus.FAILED
                self._update_content(content)
                return

            if not content.topics:
                log_error("No topics available for content")
                content.status = ContentStatus.FAILED
                self._update_content(content)
                return

            read_documents = content.reader.read(content.topics)
            if len(read_documents) > 0:
                if self.vector_db and hasattr(self.vector_db, "insert_text"):
                    # LightRAG only has async methods, use asyncio.run() here
                    result = asyncio.run(
                        self.vector_db.insert_text(
                            file_source=content.topics[0],
                            text=read_documents[0].content,
                        )
                    )
                else:
                    log_error("Vector database does not support text insertion")
                    content.status = ContentStatus.FAILED
                    self._update_content(content)
                    return
                content.external_id = result
                content.status = ContentStatus.COMPLETED
                self._update_content(content)
                return
            else:
                log_warning(f"No documents found for LightRAG upload: {content.name}")
                return
