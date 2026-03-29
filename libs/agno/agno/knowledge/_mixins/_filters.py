"""Filter validation methods for the Knowledge class.

These methods validate and retrieve filter keys from content metadata.
They depend on get_content/aget_content from the content management methods.
"""

from typing import Any, Dict, List, Set, Tuple, Union

from agno.filters import FilterExpr


class _KnowledgeFilterMixin:
    """Filter validation and retrieval methods extracted from Knowledge."""

    def get_valid_filters(self) -> Set[str]:
        from agno.utils.log import log_info

        if self.contents_db is None:
            log_info("Advanced filtering is not supported without a contents db. All filter keys considered valid.")
            return set()
        contents, _ = self.get_content()
        valid_filters: Set[str] = set()
        for content in contents:
            if content.metadata:
                valid_filters.update(content.metadata.keys())

        return valid_filters

    async def aget_valid_filters(self) -> Set[str]:
        from agno.utils.log import log_info

        if self.contents_db is None:
            log_info("Advanced filtering is not supported without a contents db. All filter keys considered valid.")
            return set()
        contents, _ = await self.aget_content()
        valid_filters: Set[str] = set()
        for content in contents:
            if content.metadata:
                valid_filters.update(content.metadata.keys())

        return valid_filters

    def validate_filters(
        self, filters: Union[Dict[str, Any], List[FilterExpr]]
    ) -> Tuple[Union[Dict[str, Any], List[FilterExpr]], List[str]]:
        valid_filters_from_db = self.get_valid_filters()

        valid_filters, invalid_keys = self._validate_filters(filters, valid_filters_from_db)

        return valid_filters, invalid_keys

    async def avalidate_filters(
        self, filters: Union[Dict[str, Any], List[FilterExpr]]
    ) -> Tuple[Union[Dict[str, Any], List[FilterExpr]], List[str]]:
        """Return a tuple containing a dict with all valid filters and a list of invalid filter keys"""
        valid_filters_from_db = await self.aget_valid_filters()

        valid_filters, invalid_keys = self._validate_filters(filters, valid_filters_from_db)

        return valid_filters, invalid_keys

    def _validate_filters(
        self, filters: Union[Dict[str, Any], List[FilterExpr]], valid_metadata_filters: Set[str]
    ) -> Tuple[Union[Dict[str, Any], List[FilterExpr]], List[str]]:
        from agno.utils.log import log_warning

        if not filters:
            return {}, []

        valid_filters: Union[Dict[str, Any], List[FilterExpr]] = {}
        invalid_keys = []

        if isinstance(filters, dict):
            # If no metadata filters tracked yet, all keys are considered invalid
            if valid_metadata_filters is None or not valid_metadata_filters:
                invalid_keys = list(filters.keys())
                log_warning(
                    f"No valid metadata filters tracked yet. All filter keys considered invalid: {invalid_keys}"
                )
                return {}, invalid_keys

            for key, value in filters.items():
                # Handle both normal keys and prefixed keys like meta_data.key
                base_key = key.split(".")[-1] if "." in key else key
                if base_key in valid_metadata_filters or key in valid_metadata_filters:
                    valid_filters[key] = value  # type: ignore
                else:
                    invalid_keys.append(key)
                    log_warning(f"Invalid filter key: {key} - not present in knowledge base")

        elif isinstance(filters, List):
            # Validate list filters against known metadata keys
            if valid_metadata_filters is None or not valid_metadata_filters:
                # Can't validate keys without metadata - return original list
                log_warning("No valid metadata filters tracked yet. Cannot validate list filter keys.")
                return filters, []

            valid_list_filters: List[FilterExpr] = []
            for i, filter_item in enumerate(filters):
                if not isinstance(filter_item, FilterExpr):
                    log_warning(
                        f"Invalid filter at index {i}: expected FilterExpr instance, "
                        f"got {type(filter_item).__name__}. "
                        "Use filter expressions like EQ('key', 'value'), IN('key', [values]), "
                        "AND(...), OR(...), NOT(...) from agno.filters"
                    )
                    continue

                # Check if filter has a key attribute and validate it
                if hasattr(filter_item, "key"):
                    key = filter_item.key
                    base_key = key.split(".")[-1] if "." in key else key
                    if base_key in valid_metadata_filters or key in valid_metadata_filters:
                        valid_list_filters.append(filter_item)
                    else:
                        invalid_keys.append(key)
                        log_warning(f"Invalid filter key: {key} - not present in knowledge base")
                else:
                    # Complex filters (AND, OR, NOT) - keep them as-is
                    # They contain nested filters that will be validated by the vector DB
                    valid_list_filters.append(filter_item)

            return valid_list_filters, invalid_keys

        return valid_filters, invalid_keys
