"""Agent protocol implementation for the Knowledge class.

These methods implement the tool interface exposed to Agent and Team instances:
- build_context / abuild_context: Generate system prompt instructions
- get_tools / aget_tools: Return search tool closures
- _create_search_tool / _create_search_tool_with_filters: Tool factories
"""

from typing import Any, Dict, List, Optional, Set, Union

from agno.filters import FilterExpr
from agno.utils.log import log_debug, log_warning


class _KnowledgeToolMixin:
    """Agent protocol: context building and search tool creation."""

    # Shared context strings
    _SEARCH_KNOWLEDGE_INSTRUCTIONS = (
        "You have a knowledge base you can search using the search_knowledge_base tool. "
        "Search before answering questions—don't assume you know the answer. "
        "For ambiguous questions, search first rather than asking for clarification."
    )

    _AGENTIC_FILTER_INSTRUCTION_TEMPLATE = """
The knowledge base contains documents with these metadata filters: {valid_filters_str}.
Always use filters when the user query indicates specific metadata.

Examples:
1. If the user asks about a specific person like "Jordan Mitchell", you MUST use the search_knowledge_base tool with the filters parameter set to {{'<valid key like user_id>': '<valid value based on the user query>'}}.
2. If the user asks about a specific document type like "contracts", you MUST use the search_knowledge_base tool with the filters parameter set to {{'document_type': 'contract'}}.
3. If the user asks about a specific location like "documents from New York", you MUST use the search_knowledge_base tool with the filters parameter set to {{'<valid key like location>': 'New York'}}.

General Guidelines:
- Always analyze the user query to identify relevant metadata.
- Use the most specific filter(s) possible to narrow down results.
- If multiple filters are relevant, combine them in the filters parameter (e.g., {{'name': 'Jordan Mitchell', 'document_type': 'contract'}}).
- Ensure the filter keys match the valid metadata filters: {valid_filters_str}.

Make sure to pass the filters as [Dict[str: Any]] to the tool. FOLLOW THIS STRUCTURE STRICTLY.
""".strip()

    def _get_agentic_filter_instructions(self, valid_filters: Set[str]) -> str:
        """Generate the agentic filter instructions for the given valid filters."""
        valid_filters_str = ", ".join(valid_filters)
        return self._AGENTIC_FILTER_INSTRUCTION_TEMPLATE.format(valid_filters_str=valid_filters_str)

    def build_context(
        self,
        enable_agentic_filters: bool = False,
        **kwargs,
    ) -> str:
        """Build context string for the agent's system prompt.

        Returns instructions about how to use the search_knowledge_base tool
        and available filters.

        Args:
            enable_agentic_filters: Whether agentic filters are enabled.
            **kwargs: Additional context (unused).

        Returns:
            Context string to add to system prompt.
        """
        context_parts: List[str] = [self._SEARCH_KNOWLEDGE_INSTRUCTIONS]

        # Add filter instructions if agentic filters are enabled
        if enable_agentic_filters:
            valid_filters = self.get_valid_filters()
            if valid_filters:
                context_parts.append(self._get_agentic_filter_instructions(valid_filters))

        return "<knowledge_base>\n" + "\n".join(context_parts) + "\n</knowledge_base>"

    async def abuild_context(
        self,
        enable_agentic_filters: bool = False,
        **kwargs,
    ) -> str:
        """Async version of build_context.

        Returns instructions about how to use the search_knowledge_base tool
        and available filters.

        Args:
            enable_agentic_filters: Whether agentic filters are enabled.
            **kwargs: Additional context (unused).

        Returns:
            Context string to add to system prompt.
        """
        context_parts: List[str] = [self._SEARCH_KNOWLEDGE_INSTRUCTIONS]

        # Add filter instructions if agentic filters are enabled
        if enable_agentic_filters:
            valid_filters = await self.aget_valid_filters()
            if valid_filters:
                context_parts.append(self._get_agentic_filter_instructions(valid_filters))

        return "<knowledge_base>\n" + "\n".join(context_parts) + "\n</knowledge_base>"

    def get_tools(
        self,
        run_response: Optional[Any] = None,
        run_context: Optional[Any] = None,
        knowledge_filters: Optional[Union[Dict[str, Any], List[FilterExpr]]] = None,
        async_mode: bool = False,
        enable_agentic_filters: bool = False,
        agent: Optional[Any] = None,
        **kwargs,
    ) -> List[Any]:
        """Get tools to expose to the Agent or Team.

        Returns the search_knowledge_base tool configured for this knowledge base.

        Args:
            run_response: The run response object to add references to.
            run_context: The run context.
            knowledge_filters: Filters to apply to searches.
            async_mode: Whether to return async tools.
            enable_agentic_filters: Whether to enable filter parameter on tool.
            agent: The Agent or Team instance (for document conversion with references_format).
            **kwargs: Additional context.

        Returns:
            List containing the search tool.
        """
        if enable_agentic_filters:
            tool = self._create_search_tool_with_filters(
                run_response=run_response,
                run_context=run_context,
                knowledge_filters=knowledge_filters,
                async_mode=async_mode,
                agent=agent,
            )
        else:
            tool = self._create_search_tool(
                run_response=run_response,
                run_context=run_context,
                knowledge_filters=knowledge_filters,
                async_mode=async_mode,
                agent=agent,
            )

        return [tool]

    async def aget_tools(
        self,
        run_response: Optional[Any] = None,
        run_context: Optional[Any] = None,
        knowledge_filters: Optional[Union[Dict[str, Any], List[FilterExpr]]] = None,
        async_mode: bool = True,
        enable_agentic_filters: bool = False,
        agent: Optional[Any] = None,
        **kwargs,
    ) -> List[Any]:
        """Async version of get_tools."""
        return self.get_tools(
            run_response=run_response,
            run_context=run_context,
            knowledge_filters=knowledge_filters,
            async_mode=async_mode,
            enable_agentic_filters=enable_agentic_filters,
            agent=agent,
            **kwargs,
        )

    def _create_search_tool(
        self,
        run_response: Optional[Any] = None,
        run_context: Optional[Any] = None,
        knowledge_filters: Optional[Union[Dict[str, Any], List[FilterExpr]]] = None,
        async_mode: bool = False,
        agent: Optional[Any] = None,
    ) -> Any:
        """Create the search_knowledge_base tool without filter parameter.

        Args:
            agent: Agent or Team instance for custom document conversion.
        """
        from agno.models.message import MessageReferences
        from agno.tools.function import Function
        from agno.utils.timer import Timer

        def search_knowledge_base(query: str) -> Union[str, Any]:
            """Use this function to search the knowledge base for information about a query.

            Args:
                query: The query to search for.

            Returns:
                str: A string containing the response from the knowledge base.
            """
            from agno.tools.function import ToolResult

            retrieval_timer = Timer()
            retrieval_timer.start()

            try:
                docs = self.search(query=query, filters=knowledge_filters)
            except Exception as e:
                retrieval_timer.stop()
                log_warning(f"Knowledge search failed: {e}")
                return f"Error searching knowledge base: {type(e).__name__}"

            if run_response is not None and docs:
                references = MessageReferences(
                    query=query,
                    references=[self._doc_to_reference_dict(doc) for doc in docs],
                    time=round(retrieval_timer.elapsed, 4),
                )
                if run_response.references is None:
                    run_response.references = []
                run_response.references.append(references)

            retrieval_timer.stop()
            log_debug(f"Time to get references: {retrieval_timer.elapsed:.4f}s")

            if not docs:
                return "No documents found"

            if self.use_page_images and docs:
                images = self._get_page_images_for_docs(docs)
                if images:
                    return ToolResult(
                        content=f"Found {len(docs)} relevant document sections across {len(images)} pages.",
                        images=images,
                    )

            return self._convert_documents_to_string(docs, agent)

        async def asearch_knowledge_base(query: str) -> Union[str, Any]:
            """Use this function to search the knowledge base for information about a query asynchronously.

            Args:
                query: The query to search for.

            Returns:
                str: A string containing the response from the knowledge base.
            """
            from agno.tools.function import ToolResult

            retrieval_timer = Timer()
            retrieval_timer.start()

            try:
                docs = await self.asearch(query=query, filters=knowledge_filters)
            except Exception as e:
                retrieval_timer.stop()
                log_warning(f"Knowledge search failed: {e}")
                return f"Error searching knowledge base: {type(e).__name__}"

            if run_response is not None and docs:
                references = MessageReferences(
                    query=query,
                    references=[await self._async_doc_to_reference_dict(doc) for doc in docs],
                    time=round(retrieval_timer.elapsed, 4),
                )
                if run_response.references is None:
                    run_response.references = []
                run_response.references.append(references)

            retrieval_timer.stop()
            log_debug(f"Time to get references: {retrieval_timer.elapsed:.4f}s")

            if not docs:
                return "No documents found"

            if self.use_page_images and docs:
                images = self._get_page_images_for_docs(docs)
                if images:
                    return ToolResult(
                        content=f"Found {len(docs)} relevant document sections across {len(images)} pages.",
                        images=images,
                    )

            return self._convert_documents_to_string(docs, agent)

        if async_mode:
            return Function.from_callable(asearch_knowledge_base, name="search_knowledge_base")
        else:
            return Function.from_callable(search_knowledge_base, name="search_knowledge_base")

    def _create_search_tool_with_filters(
        self,
        run_response: Optional[Any] = None,
        run_context: Optional[Any] = None,
        knowledge_filters: Optional[Union[Dict[str, Any], List[FilterExpr]]] = None,
        async_mode: bool = False,
        agent: Optional[Any] = None,
    ) -> Any:
        """Create the search_knowledge_base tool with filter parameter.

        Args:
            agent: Agent or Team instance for custom document conversion.
        """
        from agno.models.message import MessageReferences
        from agno.tools.function import Function
        from agno.utils.timer import Timer

        # Import here to avoid circular imports
        try:
            from agno.utils.knowledge import get_agentic_or_user_search_filters
        except ImportError:
            get_agentic_or_user_search_filters = None  # type: ignore[assignment]

        def search_knowledge_base(query: str, filters: Optional[List[Any]] = None) -> Union[str, Any]:
            """Use this function to search the knowledge base for information about a query.

            Args:
                query: The query to search for.
                filters (optional): The filters to apply to the search. This is a list of KnowledgeFilter objects.

            Returns:
                str: A string containing the response from the knowledge base.
            """
            from agno.tools.function import ToolResult

            # Merge agentic filters with user-provided filters
            search_filters: Optional[Union[Dict[str, Any], List[FilterExpr]]] = None
            if filters and get_agentic_or_user_search_filters is not None:
                # Handle both KnowledgeFilter objects and plain dictionaries
                filters_dict: Dict[str, Any] = {}
                for filt in filters:
                    if isinstance(filt, dict):
                        filters_dict.update(filt)
                    elif hasattr(filt, "key") and hasattr(filt, "value"):
                        filters_dict[filt.key] = filt.value
                search_filters = get_agentic_or_user_search_filters(filters_dict, knowledge_filters)
            else:
                search_filters = knowledge_filters

            # Validate filters if we have that capability
            if search_filters:
                validated_filters, invalid_keys = self.validate_filters(search_filters)
                if invalid_keys:
                    log_warning(f"Invalid filter keys ignored: {invalid_keys}")
                search_filters = validated_filters if validated_filters else None

            retrieval_timer = Timer()
            retrieval_timer.start()

            try:
                docs = self.search(query=query, filters=search_filters)
            except Exception as e:
                retrieval_timer.stop()
                log_warning(f"Knowledge search failed: {e}")
                return f"Error searching knowledge base: {type(e).__name__}"

            if run_response is not None and docs:
                references = MessageReferences(
                    query=query,
                    references=[self._doc_to_reference_dict(doc) for doc in docs],
                    time=round(retrieval_timer.elapsed, 4),
                )
                if run_response.references is None:
                    run_response.references = []
                run_response.references.append(references)

            retrieval_timer.stop()
            log_debug(f"Time to get references: {retrieval_timer.elapsed:.4f}s")

            if not docs:
                return "No documents found"

            if self.use_page_images and docs:
                images = self._get_page_images_for_docs(docs)
                if images:
                    return ToolResult(
                        content=f"Found {len(docs)} relevant document sections across {len(images)} pages.",
                        images=images,
                    )

            return self._convert_documents_to_string(docs, agent)

        async def asearch_knowledge_base(query: str, filters: Optional[List[Any]] = None) -> Union[str, Any]:
            """Use this function to search the knowledge base for information about a query asynchronously.

            Args:
                query: The query to search for.
                filters (optional): The filters to apply to the search. This is a list of KnowledgeFilter objects.

            Returns:
                str: A string containing the response from the knowledge base.
            """
            from agno.tools.function import ToolResult

            # Merge agentic filters with user-provided filters
            search_filters: Optional[Union[Dict[str, Any], List[FilterExpr]]] = None
            if filters and get_agentic_or_user_search_filters is not None:
                # Handle both KnowledgeFilter objects and plain dictionaries
                filters_dict: Dict[str, Any] = {}
                for filt in filters:
                    if isinstance(filt, dict):
                        filters_dict.update(filt)
                    elif hasattr(filt, "key") and hasattr(filt, "value"):
                        filters_dict[filt.key] = filt.value
                search_filters = get_agentic_or_user_search_filters(filters_dict, knowledge_filters)
            else:
                search_filters = knowledge_filters

            # Validate filters if we have that capability
            if search_filters:
                validated_filters, invalid_keys = await self.avalidate_filters(search_filters)
                if invalid_keys:
                    log_warning(f"Invalid filter keys ignored: {invalid_keys}")
                search_filters = validated_filters if validated_filters else None

            retrieval_timer = Timer()
            retrieval_timer.start()

            try:
                docs = await self.asearch(query=query, filters=search_filters)
            except Exception as e:
                retrieval_timer.stop()
                log_warning(f"Knowledge search failed: {e}")
                return f"Error searching knowledge base: {type(e).__name__}"

            if run_response is not None and docs:
                references = MessageReferences(
                    query=query,
                    references=[await self._async_doc_to_reference_dict(doc) for doc in docs],
                    time=round(retrieval_timer.elapsed, 4),
                )
                if run_response.references is None:
                    run_response.references = []
                run_response.references.append(references)

            retrieval_timer.stop()
            log_debug(f"Time to get references: {retrieval_timer.elapsed:.4f}s")

            if not docs:
                return "No documents found"

            if self.use_page_images and docs:
                images = self._get_page_images_for_docs(docs)
                if images:
                    return ToolResult(
                        content=f"Found {len(docs)} relevant document sections across {len(images)} pages.",
                        images=images,
                    )

            return self._convert_documents_to_string(docs, agent)

        if async_mode:
            func = Function.from_callable(asearch_knowledge_base, name="search_knowledge_base")
        else:
            func = Function.from_callable(search_knowledge_base, name="search_knowledge_base")

        # Opt out of strict mode since filters use dynamic types that are incompatible with strict mode
        func.strict = False
        return func
