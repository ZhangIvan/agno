"""Topic loading methods for the Knowledge class."""

from typing import cast

from agno.knowledge.content import Content, ContentStatus, FileData
from agno.knowledge.types import KnowledgeContentOrigin
from agno.utils.log import log_error, log_info, log_warning
from agno.utils.string import generate_id


class _KnowledgeTopicLoaderMixin:
    """Topic loading methods extracted from _KnowledgeLoadingMixin."""

    async def _aload_from_topics(
        self,
        content: Content,
        upsert: bool,
        skip_if_exists: bool,
    ):
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)
        log_info(f"Adding content from topics: {content.topics}")

        if content.topics is None:
            log_warning("No topics provided for content")
            return

        for topic in content.topics:
            content = Content(
                name=topic,
                metadata=content.metadata,
                reader=content.reader,
                status=ContentStatus.PROCESSING if content.reader else ContentStatus.FAILED,
                file_data=FileData(
                    type="Topic",
                ),
                topics=[topic],
            )
            content.content_hash = self._build_content_hash(content)
            content.id = generate_id(content.content_hash)

            await self._ainsert_contents_db(content)
            if await self._async_should_skip(content.content_hash, skip_if_exists):
                content.status = ContentStatus.COMPLETED
                await self._aupdate_content(content)
                continue  # Skip to next topic, don't exit loop

            if self.vector_db.__class__.__name__ == "LightRag":
                await self._aprocess_lightrag_content(content, KnowledgeContentOrigin.TOPIC)
                continue  # Skip to next topic, don't exit loop

            if content.reader is None:
                log_error(f"No reader available for topic: {topic}")
                content.status = ContentStatus.FAILED
                content.status_message = "No reader available for topic"
                await self._aupdate_content(content)
                continue

            read_documents = await content.reader.async_read(topic)
            if len(read_documents) > 0:
                self._prepare_documents_for_insert(read_documents, content.id, calculate_sizes=True)
            else:
                content.status = ContentStatus.FAILED
                content.status_message = "No content found for topic"
                await self._aupdate_content(content)

            await self._ahandle_vector_db_insert(content, read_documents, upsert)

    def _load_from_topics(
        self,
        content: Content,
        upsert: bool,
        skip_if_exists: bool,
    ):
        """Synchronous version of _load_from_topics."""
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)
        log_info(f"Adding content from topics: {content.topics}")

        if content.topics is None:
            log_warning("No topics provided for content")
            return

        for topic in content.topics:
            content = Content(
                name=topic,
                metadata=content.metadata,
                reader=content.reader,
                status=ContentStatus.PROCESSING if content.reader else ContentStatus.FAILED,
                file_data=FileData(
                    type="Topic",
                ),
                topics=[topic],
            )
            content.content_hash = self._build_content_hash(content)
            content.id = generate_id(content.content_hash)

            self._insert_contents_db(content)
            if self._should_skip(content.content_hash, skip_if_exists):
                content.status = ContentStatus.COMPLETED
                self._update_content(content)
                continue  # Skip to next topic, don't exit loop

            if self.vector_db.__class__.__name__ == "LightRag":
                self._process_lightrag_content(content, KnowledgeContentOrigin.TOPIC)
                continue  # Skip to next topic, don't exit loop

            if content.reader is None:
                log_error(f"No reader available for topic: {topic}")
                content.status = ContentStatus.FAILED
                content.status_message = "No reader available for topic"
                self._update_content(content)
                continue

            read_documents = content.reader.read(topic)
            if len(read_documents) > 0:
                self._prepare_documents_for_insert(read_documents, content.id, calculate_sizes=True)
            else:
                content.status = ContentStatus.FAILED
                content.status_message = "No content found for topic"
                self._update_content(content)

            self._handle_vector_db_insert(content, read_documents, upsert)
