"""Deprecated backward-compatible methods for the Knowledge class.

These methods are thin wrappers around the current API (insert, ainsert, ainsert_many).
They exist solely for backward compatibility and should not be used in new code.
"""

from typing import Any, Dict, List, Optional, Union, overload

from agno.knowledge.content import ContentAuth
from agno.knowledge.reader.base import Reader
from agno.knowledge.remote_content.remote_content import RemoteContent


# Type alias matching knowledge.py
ContentDict = Dict[str, Union[str, Dict[str, str]]]


class _KnowledgeDeprecatedMixin:
    """Backward-compatible wrappers for the insert API.

    .. deprecated::
        Use ``insert()``, ``ainsert()``, and ``ainsert_many()`` instead.
    """

    @overload
    def add_content(
        self,
        *,
        path: Optional[str] = None,
        url: Optional[str] = None,
        text_content: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        upsert: bool = True,
        skip_if_exists: bool = False,
        reader: Optional[Reader] = None,
        auth: Optional[ContentAuth] = None,
    ) -> None: ...

    @overload
    def add_content(self, *args, **kwargs) -> None: ...

    def add_content(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        path: Optional[str] = None,
        url: Optional[str] = None,
        text_content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        topics: Optional[List[str]] = None,
        remote_content: Optional[RemoteContent] = None,
        reader: Optional[Reader] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        upsert: bool = True,
        skip_if_exists: bool = False,
        auth: Optional[ContentAuth] = None,
    ) -> None:
        """
        DEPRECATED: Use ``insert()`` instead.

        This method will be removed in a future version.
        """
        return self.insert(
            name=name,
            description=description,
            path=path,
            url=url,
            text_content=text_content,
            metadata=metadata,
            topics=topics,
            remote_content=remote_content,
            reader=reader,
            include=include,
            exclude=exclude,
            upsert=upsert,
            skip_if_exists=skip_if_exists,
            auth=auth,
        )

    @overload
    async def add_content_async(
        self,
        *,
        path: Optional[str] = None,
        url: Optional[str] = None,
        text_content: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        upsert: bool = True,
        skip_if_exists: bool = False,
        reader: Optional[Reader] = None,
        auth: Optional[ContentAuth] = None,
    ) -> None: ...

    @overload
    async def add_content_async(self, *args, **kwargs) -> None: ...

    async def add_content_async(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        path: Optional[str] = None,
        url: Optional[str] = None,
        text_content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        topics: Optional[List[str]] = None,
        remote_content: Optional[RemoteContent] = None,
        reader: Optional[Reader] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        upsert: bool = True,
        skip_if_exists: bool = False,
        auth: Optional[ContentAuth] = None,
    ) -> None:
        """
        DEPRECATED: Use ``ainsert()`` instead.

        This method will be removed in a future version.
        """
        return await self.ainsert(
            name=name,
            description=description,
            path=path,
            url=url,
            text_content=text_content,
            metadata=metadata,
            topics=topics,
            remote_content=remote_content,
            reader=reader,
            include=include,
            exclude=exclude,
            upsert=upsert,
            skip_if_exists=skip_if_exists,
            auth=auth,
        )

    @overload
    async def add_contents_async(self, contents: List[ContentDict]) -> None: ...

    @overload
    async def add_contents_async(
        self,
        *,
        paths: Optional[List[str]] = None,
        urls: Optional[List[str]] = None,
        metadata: Optional[Dict[str, str]] = None,
        topics: Optional[List[str]] = None,
        text_contents: Optional[List[str]] = None,
        reader: Optional[Reader] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        upsert: bool = True,
        skip_if_exists: bool = False,
        remote_content: Optional[RemoteContent] = None,
    ) -> None: ...

    async def add_contents_async(self, *args, **kwargs) -> None:
        """
        DEPRECATED: Use ``ainsert_many()`` instead.

        This method will be removed in a future version.
        """
        return await self.ainsert_many(*args, **kwargs)
