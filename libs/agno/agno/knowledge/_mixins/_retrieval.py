"""Document retrieval helpers for the Knowledge class.

These methods handle converting retrieved documents to various output formats
used by the search tools and agent protocol.
"""

from typing import Any, List, Optional

from agno.knowledge.document import Document


class _KnowledgeRetrievalMixin:
    """Document conversion and retrieval formatting helpers."""

    def _convert_documents_to_string(
        self,
        docs: List[Document],
        agent: Optional[Any] = None,
    ) -> str:
        """Convert documents to a string representation.

        Args:
            docs: List of documents to convert.
            agent: Optional Agent or Team instance for custom conversion using their references_format.

        Returns:
            String representation of documents.
        """
        # If agent (Agent or Team) has a custom converter, use it for proper YAML/JSON formatting
        if agent is not None and hasattr(agent, "_convert_documents_to_string"):
            return agent._convert_documents_to_string([doc.to_dict() for doc in docs])

        # Default conversion
        if not docs:
            return "No documents found"

        result_parts = []
        for doc in docs:
            if doc.content:
                result_parts.append(doc.content)

        return "\n\n---\n\n".join(result_parts) if result_parts else "No content found"
