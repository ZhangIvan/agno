"""Content management methods for the Knowledge class.

These methods handle CRUD operations for knowledge content
including retrieval, status checking, patching, and removal.
"""

from typing import Any, Dict, List, Optional, Tuple, cast

from agno.db.base import AsyncBaseDb
from agno.knowledge.content import Content, ContentStatus
from agno.utils.log import log_warning


class _KnowledgeContentManagementMixin:
    """Content management methods extracted from Knowledge."""

    def get_content(
        self,
        limit: Optional[int] = None,
        page: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Tuple[List[Content], int]:
        if self.contents_db is None:
            raise ValueError("No contents db provided")

        if isinstance(self.contents_db, AsyncBaseDb):
            raise ValueError("get_content() is not supported for async databases. Please use aget_content() instead.")

        # Filter by linked_to when knowledge has a name for isolation
        contents, count = self.contents_db.get_knowledge_contents(
            limit=limit, page=page, sort_by=sort_by, sort_order=sort_order, linked_to=self.name
        )
        return [self._content_row_to_content(row) for row in contents], count

    async def aget_content(
        self,
        limit: Optional[int] = None,
        page: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Tuple[List[Content], int]:
        if self.contents_db is None:
            raise ValueError("No contents db provided")

        # Filter by linked_to when knowledge has a name for isolation
        if isinstance(self.contents_db, AsyncBaseDb):
            contents, count = await self.contents_db.get_knowledge_contents(
                limit=limit, page=page, sort_by=sort_by, sort_order=sort_order, linked_to=self.name
            )
        else:
            contents, count = self.contents_db.get_knowledge_contents(
                limit=limit, page=page, sort_by=sort_by, sort_order=sort_order, linked_to=self.name
            )
        return [self._content_row_to_content(row) for row in contents], count

    def get_content_by_id(self, content_id: str) -> Optional[Content]:
        if self.contents_db is None:
            raise ValueError("No contents db provided")

        if isinstance(self.contents_db, AsyncBaseDb):
            raise ValueError(
                "get_content_by_id() is not supported for async databases. Please use aget_content_by_id() instead."
            )

        content_row = self.contents_db.get_knowledge_content(content_id)
        if content_row is None:
            return None
        return self._content_row_to_content(content_row)

    async def aget_content_by_id(self, content_id: str) -> Optional[Content]:
        if self.contents_db is None:
            raise ValueError("No contents db provided")

        if isinstance(self.contents_db, AsyncBaseDb):
            content_row = await self.contents_db.get_knowledge_content(content_id)
        else:
            content_row = self.contents_db.get_knowledge_content(content_id)

        if content_row is None:
            return None
        return self._content_row_to_content(content_row)

    def get_content_status(self, content_id: str) -> Tuple[Optional[ContentStatus], Optional[str]]:
        if self.contents_db is None:
            raise ValueError("No contents db provided")

        if isinstance(self.contents_db, AsyncBaseDb):
            raise ValueError(
                "get_content_status() is not supported for async databases. Please use aget_content_status() instead."
            )

        content_row = self.contents_db.get_knowledge_content(content_id)
        if content_row is None:
            return None, "Content not found"

        return self._parse_content_status(content_row.status), content_row.status_message

    async def aget_content_status(self, content_id: str) -> Tuple[Optional[ContentStatus], Optional[str]]:
        if self.contents_db is None:
            raise ValueError("No contents db provided")

        if isinstance(self.contents_db, AsyncBaseDb):
            content_row = await self.contents_db.get_knowledge_content(content_id)
        else:
            content_row = self.contents_db.get_knowledge_content(content_id)

        if content_row is None:
            return None, "Content not found"

        return self._parse_content_status(content_row.status), content_row.status_message

    def patch_content(self, content: Content) -> Optional[Dict[str, Any]]:
        return self._update_content(content)

    async def apatch_content(self, content: Content) -> Optional[Dict[str, Any]]:
        return await self._aupdate_content(content)

    def remove_content_by_id(self, content_id: str):
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)
        if self.vector_db is not None:
            if self.vector_db.__class__.__name__ == "LightRag":
                # For LightRAG, get the content first to find the external_id
                content = self.get_content_by_id(content_id)
                if content and content.external_id:
                    self.vector_db.delete_by_external_id(content.external_id)  # type: ignore
                else:
                    log_warning(f"No external_id found for content {content_id}, cannot delete from LightRAG")
            else:
                self.vector_db.delete_by_content_id(content_id)

        if self.contents_db is not None:
            self.contents_db.delete_knowledge_content(content_id)

    async def aremove_content_by_id(self, content_id: str):
        if self.vector_db is not None:
            if self.vector_db.__class__.__name__ == "LightRag":
                # For LightRAG, get the content first to find the external_id
                content = await self.aget_content_by_id(content_id)
                if content and content.external_id:
                    self.vector_db.delete_by_external_id(content.external_id)  # type: ignore
                else:
                    log_warning(f"No external_id found for content {content_id}, cannot delete from LightRAG")
            else:
                self.vector_db.delete_by_content_id(content_id)

        if self.contents_db is not None:
            if isinstance(self.contents_db, AsyncBaseDb):
                await self.contents_db.delete_knowledge_content(content_id)
            else:
                self.contents_db.delete_knowledge_content(content_id)

    def remove_all_content(self):
        contents, _ = self.get_content()
        for content in contents:
            if content.id is not None:
                self.remove_content_by_id(content.id)

    async def aremove_all_content(self):
        contents, _ = await self.aget_content()
        for content in contents:
            if content.id is not None:
                await self.aremove_content_by_id(content.id)

    def remove_vector_by_id(self, id: str) -> bool:
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)
        if self.vector_db is None:
            log_warning("No vector DB provided")
            return False
        return self.vector_db.delete_by_id(id)

    def remove_vectors_by_name(self, name: str) -> bool:
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)
        if self.vector_db is None:
            log_warning("No vector DB provided")
            return False
        return self.vector_db.delete_by_name(name)

    def remove_vectors_by_metadata(self, metadata: Dict[str, Any]) -> bool:
        from agno.vectordb import VectorDb

        self.vector_db = cast(VectorDb, self.vector_db)
        if self.vector_db is None:
            log_warning("No vector DB provided")
            return False
        return self.vector_db.delete_by_metadata(metadata)
