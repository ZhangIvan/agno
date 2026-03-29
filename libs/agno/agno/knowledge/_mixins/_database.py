"""Database operation methods for the Knowledge class.

These methods handle interactions with the contents database
and vector database, including insertion and content updates.
"""

import time
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

from agno.db.base import AsyncBaseDb
from agno.knowledge.content import Content, ContentStatus
from agno.knowledge.utils import merge_user_metadata, strip_agno_metadata
from agno.utils.log import log_error, log_warning


class _KnowledgeDatabaseMixin:
    """Database operation methods extracted from Knowledge."""

    async def _ainsert_contents_db(self, content: Content):
        if self.contents_db:
            content_row = self._build_knowledge_row(content)
            if isinstance(self.contents_db, AsyncBaseDb):
                await self.contents_db.upsert_knowledge_content(knowledge_row=content_row)
            else:
                self.contents_db.upsert_knowledge_content(knowledge_row=content_row)

    def _insert_contents_db(self, content: Content):
        """Synchronously add content to contents database."""
        if self.contents_db:
            if isinstance(self.contents_db, AsyncBaseDb):
                raise ValueError(
                    "_insert_contents_db() is not supported with an async DB. Please use ainsert() with AsyncDb."
                )
            content_row = self._build_knowledge_row(content)
            self.contents_db.upsert_knowledge_content(knowledge_row=content_row)

    # --- Vector DB Insert Helpers ---

    async def _ahandle_vector_db_insert(
        self,
        content: Content,
        read_documents,
        upsert,
        file_source: Optional[Union[Path, BytesIO]] = None,
    ):
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)

        if not self.vector_db:
            log_error("No vector database configured")
            content.status = ContentStatus.FAILED
            content.status_message = "No vector database configured"
            await self._aupdate_content(content)
            return

        # Upload original file to OSS (if storage configured and source available)
        if self.page_image_storage and file_source is not None:
            read_documents = await self._async_upload_original_file(content, file_source, read_documents)

        local_page_paths: List[str] = []
        if self.page_image_storage:
            read_documents, local_page_paths = await self._async_upload_page_images(read_documents)

        if self.vector_db.upsert_available() and upsert:
            try:
                await self.vector_db.async_upsert(content.content_hash, read_documents, content.metadata)  # type: ignore[arg-type]
            except Exception as e:
                log_error(f"Error upserting document: {e}")
                content.status = ContentStatus.FAILED
                content.status_message = "Could not upsert embedding"
                await self._aupdate_content(content)
                # Rollback: clean up local temp files; log orphaned OSS files
                if local_page_paths:
                    await self._async_cleanup_local_page_images(read_documents, local_page_paths)
                log_warning("VectorDB upsert failed — uploaded OSS files may be orphaned")
                return
        else:
            try:
                await self.vector_db.async_insert(
                    content.content_hash,  # type: ignore[arg-type]
                    documents=read_documents,
                    filters=content.metadata,  # type: ignore[arg-type]
                )
            except Exception as e:
                log_error(f"Error inserting document: {e}")
                content.status = ContentStatus.FAILED
                content.status_message = "Could not insert embedding"
                await self._aupdate_content(content)
                if local_page_paths:
                    await self._async_cleanup_local_page_images(read_documents, local_page_paths)
                log_warning("VectorDB insert failed — uploaded OSS files may be orphaned")
                return

        if local_page_paths:
            await self._async_cleanup_local_page_images(read_documents, local_page_paths)

        content.status = ContentStatus.COMPLETED
        await self._aupdate_content(content)

    def _handle_vector_db_insert(
        self,
        content: Content,
        read_documents,
        upsert,
        file_source: Optional[Union[Path, BytesIO]] = None,
    ):
        """Synchronously handle vector database insertion."""
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)

        if not self.vector_db:
            log_error("No vector database configured")
            content.status = ContentStatus.FAILED
            content.status_message = "No vector database configured"
            self._update_content(content)
            return

        # Upload original file to OSS (if storage configured and source available)
        if self.page_image_storage and file_source is not None:
            read_documents = self._upload_original_file(content, file_source, read_documents)

        local_page_paths: List[str] = []
        if self.page_image_storage:
            read_documents, local_page_paths = self._upload_page_images(read_documents)

        if self.vector_db.upsert_available() and upsert:
            try:
                self.vector_db.upsert(content.content_hash, read_documents, content.metadata)  # type: ignore[arg-type]
            except Exception as e:
                log_error(f"Error upserting document: {e}")
                content.status = ContentStatus.FAILED
                content.status_message = "Could not upsert embedding"
                self._update_content(content)
                # Rollback: clean up local temp files; log orphaned OSS files
                if local_page_paths:
                    self._cleanup_local_page_images(read_documents, local_page_paths)
                log_warning("VectorDB upsert failed — uploaded OSS files may be orphaned")
                return
        else:
            try:
                self.vector_db.insert(
                    content.content_hash,  # type: ignore[arg-type]
                    documents=read_documents,
                    filters=content.metadata,  # type: ignore[arg-type]
                )
            except Exception as e:
                log_error(f"Error inserting document: {e}")
                content.status = ContentStatus.FAILED
                content.status_message = "Could not insert embedding"
                self._update_content(content)
                if local_page_paths:
                    self._cleanup_local_page_images(read_documents, local_page_paths)
                log_warning("VectorDB insert failed — uploaded OSS files may be orphaned")
                return

        if local_page_paths:
            self._cleanup_local_page_images(read_documents, local_page_paths)

        content.status = ContentStatus.COMPLETED
        self._update_content(content)

    # --- Content Update ---

    def _update_content(self, content: Content) -> Optional[Dict[str, Any]]:
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)
        if self.contents_db:
            if isinstance(self.contents_db, AsyncBaseDb):
                raise ValueError(
                    "update_content() is not supported with an async DB. Please use aupdate_content() instead."
                )

            if not content.id:
                log_warning("Content id is required to update Knowledge content")
                return None

            # TODO: we shouldn't check for content here, we should trust the upsert method to handle conflicts
            content_row = self.contents_db.get_knowledge_content(content.id)
            if content_row is None:
                log_warning(f"Content row not found for id: {content.id}, cannot update status")
                return None

            # Apply safe string handling for updates as well
            if content.name is not None:
                content_row.name = self._ensure_string_field(content.name, "content.name", default="")
            if content.description is not None:
                content_row.description = self._ensure_string_field(
                    content.description, "content.description", default=""
                )
            if content.metadata is not None:
                content_row.metadata = merge_user_metadata(content_row.metadata, content.metadata)
            if content.status is not None:
                content_row.status = content.status
            if content.status_message is not None:
                content_row.status_message = self._ensure_string_field(
                    content.status_message, "content.status_message", default=""
                )
            if content.external_id is not None:
                content_row.external_id = self._ensure_string_field(
                    content.external_id, "content.external_id", default=""
                )
            content_row.updated_at = int(time.time())
            self.contents_db.upsert_knowledge_content(knowledge_row=content_row)

            if self.vector_db:
                # Strip _agno from metadata sent to vector_db — only user fields should be searchable
                user_metadata = strip_agno_metadata(content.metadata) or {}
                self.vector_db.update_metadata(content_id=content.id, metadata=user_metadata)

            return content_row.to_dict()

        else:
            return None

    async def _aupdate_content(self, content: Content) -> Optional[Dict[str, Any]]:
        if self.contents_db:
            if not content.id:
                log_warning("Content id is required to update Knowledge content")
                return None

            # TODO: we shouldn't check for content here, we should trust the upsert method to handle conflicts
            if isinstance(self.contents_db, AsyncBaseDb):
                content_row = await self.contents_db.get_knowledge_content(content.id)
            else:
                content_row = self.contents_db.get_knowledge_content(content.id)
            if content_row is None:
                log_warning(f"Content row not found for id: {content.id}, cannot update status")
                return None

            # Apply safe string handling for updates
            if content.name is not None:
                content_row.name = self._ensure_string_field(content.name, "content.name", default="")
            if content.description is not None:
                content_row.description = self._ensure_string_field(
                    content.description, "content.description", default=""
                )
            if content.metadata is not None:
                content_row.metadata = merge_user_metadata(content_row.metadata, content.metadata)
            if content.status is not None:
                content_row.status = content.status
            if content.status_message is not None:
                content_row.status_message = self._ensure_string_field(
                    content.status_message, "content.status_message", default=""
                )
            if content.external_id is not None:
                content_row.external_id = self._ensure_string_field(
                    content.external_id, "content.external_id", default=""
                )

            content_row.updated_at = int(time.time())
            if isinstance(self.contents_db, AsyncBaseDb):
                await self.contents_db.upsert_knowledge_content(knowledge_row=content_row)
            else:
                self.contents_db.upsert_knowledge_content(knowledge_row=content_row)

            if self.vector_db:
                # Strip _agno from metadata sent to vector_db — only user fields should be searchable
                user_metadata = strip_agno_metadata(content.metadata) or {}
                self.vector_db.update_metadata(content_id=content.id, metadata=user_metadata)

            return content_row.to_dict()

        else:
            return None
