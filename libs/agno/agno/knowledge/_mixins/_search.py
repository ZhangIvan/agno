"""Search and retrieval methods for the Knowledge class.

These methods handle vector search and document retrieval.
"""

import asyncio
from typing import Any, Dict, List, Optional, Union, cast

from agno.filters import EQ, FilterExpr
from agno.knowledge.document import Document
from agno.utils.log import log_debug, log_error, log_info, log_warning


class _KnowledgeSearchMixin:
    """Search and retrieval methods extracted from Knowledge."""

    def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        filters: Optional[Union[Dict[str, Any], List[FilterExpr]]] = None,
        search_type: Optional[str] = None,
    ) -> List[Document]:
        """Returns relevant documents matching a query"""
        from agno.vectordb import VectorDb
        from agno.vectordb.search import SearchType

        self.vector_db = cast(VectorDb, self.vector_db)

        if (
            hasattr(self.vector_db, "search_type")
            and isinstance(self.vector_db.search_type, SearchType)
            and search_type
        ):
            self.vector_db.search_type = SearchType(search_type)
        try:
            if self.vector_db is None:
                log_warning("No vector db provided")
                return []

            # Inject linked_to filter when isolate_vector_search is enabled and knowledge has a name
            search_filters = filters
            if self.isolate_vector_search and self.name:
                if search_filters is None:
                    search_filters = {"linked_to": self.name}
                elif isinstance(search_filters, dict):
                    search_filters = {**search_filters, "linked_to": self.name}
                elif isinstance(search_filters, list):
                    search_filters = [EQ("linked_to", self.name), *search_filters]

            _max_results = max_results or self.max_results
            log_debug(f"Getting {_max_results} relevant documents for query: {query}")
            return self.vector_db.search(query=query, limit=_max_results, filters=search_filters)
        except Exception as e:
            log_error(f"Error searching for documents: {e}")
            return []

    async def asearch(
        self,
        query: str,
        max_results: Optional[int] = None,
        filters: Optional[Union[Dict[str, Any], List[FilterExpr]]] = None,
        search_type: Optional[str] = None,
    ) -> List[Document]:
        """Returns relevant documents matching a query"""
        from agno.vectordb import VectorDb
        from agno.vectordb.search import SearchType

        self.vector_db = cast(VectorDb, self.vector_db)
        if (
            hasattr(self.vector_db, "search_type")
            and isinstance(self.vector_db.search_type, SearchType)
            and search_type
        ):
            self.vector_db.search_type = SearchType(search_type)
        try:
            if self.vector_db is None:
                log_warning("No vector db provided")
                return []

            # Inject linked_to filter when isolate_vector_search is enabled and knowledge has a name
            search_filters = filters
            if self.isolate_vector_search and self.name:
                if search_filters is None:
                    search_filters = {"linked_to": self.name}
                elif isinstance(search_filters, dict):
                    search_filters = {**search_filters, "linked_to": self.name}
                elif isinstance(search_filters, list):
                    search_filters = [EQ("linked_to", self.name), *search_filters]

            _max_results = max_results or self.max_results
            log_debug(f"Getting {_max_results} relevant documents for query: {query}")
            try:
                return await self.vector_db.async_search(query=query, limit=_max_results, filters=search_filters)
            except NotImplementedError:
                log_info("Vector db does not support async search")
                return await asyncio.to_thread(
                    self.vector_db.search, query=query, limit=_max_results, filters=search_filters
                )
        except Exception as e:
            log_error(f"Error searching for documents: {e}")
            return []

    def retrieve(
        self,
        query: str,
        max_results: Optional[int] = None,
        filters: Optional[Union[Dict[str, Any], List[FilterExpr]]] = None,
        **kwargs,
    ) -> List[Document]:
        """Retrieve documents for context injection.

        Used by the add_knowledge_to_context feature to pre-fetch
        relevant documents into the user message.

        Args:
            query: The query string.
            max_results: Maximum number of results.
            filters: Filters to apply.
            **kwargs: Additional parameters.

        Returns:
            List of Document objects.
        """
        return self.search(query=query, max_results=max_results, filters=filters)

    async def aretrieve(
        self,
        query: str,
        max_results: Optional[int] = None,
        filters: Optional[Union[Dict[str, Any], List[FilterExpr]]] = None,
        **kwargs,
    ) -> List[Document]:
        """Async version of retrieve.

        Args:
            query: The query string.
            max_results: Maximum number of results.
            filters: Filters to apply.
            **kwargs: Additional parameters.

        Returns:
            List of Document objects.
        """
        return await self.asearch(query=query, max_results=max_results, filters=filters)
