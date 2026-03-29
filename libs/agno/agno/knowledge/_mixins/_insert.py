"""Public insert API for the Knowledge class.

These methods are the primary entry points for adding content to the knowledge base:
- insert / ainsert: Insert a single content item
- insert_many / ainsert_many: Insert multiple content items (batch)
"""

from typing import Any, Dict, List, Optional, Union, overload

from agno.knowledge.content import Content, ContentAuth, FileData
from agno.knowledge.reader import Reader
from agno.knowledge.remote_content.remote_content import RemoteContent
from agno.knowledge.utils import strip_agno_metadata
from agno.utils.log import log_debug, log_warning
from agno.utils.string import generate_id

ContentDict = Dict[str, Union[str, Dict[str, str]]]


class _KnowledgeInsertMixin:
    """Public insert API: insert, ainsert, insert_many, ainsert_many."""

    # --- Insert (Single Content) ---
    @overload
    def insert(
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
    def insert(self, *args, **kwargs) -> None: ...

    def insert(
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
        Synchronously insert content into the knowledge base.

        Args:
            name: Optional name for the content
            description: Optional description for the content
            path: Optional file path to load content from
            url: Optional URL to load content from
            text_content: Optional text content to insert directly
            metadata: Optional metadata dictionary
            topics: Optional list of topics
            remote_content: Optional cloud storage configuration
            reader: Optional custom reader for processing the content
            include: Optional list of file patterns to include
            exclude: Optional list of file patterns to exclude
            upsert: Whether to update existing content if it already exists (only used when skip_if_exists=False)
            skip_if_exists: Whether to skip inserting content if it already exists (default: False)
        """
        # Validation: At least one of the parameters must be provided
        if all(argument is None for argument in [path, url, text_content, topics, remote_content]):
            log_warning(
                "At least one of 'path', 'url', 'text_content', 'topics', or 'remote_content' must be provided."
            )
            return

        # Strip reserved _agno key from user-provided metadata
        safe_metadata = strip_agno_metadata(metadata)

        content = None
        file_data = None
        if text_content:
            file_data = FileData(content=text_content, type="Text")

        content = Content(
            name=name,
            description=description,
            path=path,
            url=url,
            file_data=file_data if file_data else None,
            metadata=safe_metadata,
            topics=topics,
            remote_content=remote_content,
            reader=reader,
            auth=auth,
        )
        content.content_hash = self._build_content_hash(content)
        content.id = generate_id(content.content_hash)

        self._load_content(content, upsert, skip_if_exists, include, exclude)

    @overload
    async def ainsert(
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
    async def ainsert(self, *args, **kwargs) -> None: ...

    async def ainsert(
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
        # Validation: At least one of the parameters must be provided
        if all(argument is None for argument in [path, url, text_content, topics, remote_content]):
            log_warning(
                "At least one of 'path', 'url', 'text_content', 'topics', or 'remote_content' must be provided."
            )
            return

        # Strip reserved _agno key from user-provided metadata
        safe_metadata = strip_agno_metadata(metadata)

        content = None
        file_data = None
        if text_content:
            file_data = FileData(content=text_content, type="Text")

        content = Content(
            name=name,
            description=description,
            path=path,
            url=url,
            file_data=file_data if file_data else None,
            metadata=safe_metadata,
            topics=topics,
            remote_content=remote_content,
            reader=reader,
            auth=auth,
        )
        content.content_hash = self._build_content_hash(content)
        content.id = generate_id(content.content_hash)

        await self._aload_content(content, upsert, skip_if_exists, include, exclude)

    # --- Insert Many ---
    @overload
    async def ainsert_many(self, contents: List[ContentDict]) -> None: ...

    @overload
    async def ainsert_many(
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

    async def ainsert_many(self, *args, **kwargs) -> None:
        if args and isinstance(args[0], list):
            arguments = args[0]
            upsert = kwargs.get("upsert", True)
            skip_if_exists = kwargs.get("skip_if_exists", False)
            for argument in arguments:
                await self.ainsert(
                    name=argument.get("name"),
                    description=argument.get("description"),
                    path=argument.get("path"),
                    url=argument.get("url"),
                    metadata=argument.get("metadata"),
                    topics=argument.get("topics"),
                    text_content=argument.get("text_content"),
                    reader=argument.get("reader"),
                    include=argument.get("include"),
                    exclude=argument.get("exclude"),
                    upsert=argument.get("upsert", upsert),
                    skip_if_exists=argument.get("skip_if_exists", skip_if_exists),
                    remote_content=argument.get("remote_content", None),
                    auth=argument.get("auth"),
                )

        elif kwargs:
            name = kwargs.get("name", [])
            metadata = kwargs.get("metadata", {})
            description = kwargs.get("description", [])
            topics = kwargs.get("topics", [])
            reader = kwargs.get("reader", None)
            paths = kwargs.get("paths", [])
            urls = kwargs.get("urls", [])
            text_contents = kwargs.get("text_contents", [])
            include = kwargs.get("include")
            exclude = kwargs.get("exclude")
            upsert = kwargs.get("upsert", True)
            skip_if_exists = kwargs.get("skip_if_exists", False)
            remote_content = kwargs.get("remote_content", None)
            auth = kwargs.get("auth")
            for path in paths:
                await self.ainsert(
                    name=name,
                    description=description,
                    path=path,
                    metadata=metadata,
                    include=include,
                    exclude=exclude,
                    upsert=upsert,
                    skip_if_exists=skip_if_exists,
                    reader=reader,
                    auth=auth,
                )
            for url in urls:
                await self.ainsert(
                    name=name,
                    description=description,
                    url=url,
                    metadata=metadata,
                    include=include,
                    exclude=exclude,
                    upsert=upsert,
                    skip_if_exists=skip_if_exists,
                    reader=reader,
                    auth=auth,
                )
            for i, text_content in enumerate(text_contents):
                content_name = f"{name}_{i}" if name else f"text_content_{i}"
                log_debug(f"Adding text content: {content_name}")
                await self.ainsert(
                    name=content_name,
                    description=description,
                    text_content=text_content,
                    metadata=metadata,
                    include=include,
                    exclude=exclude,
                    upsert=upsert,
                    skip_if_exists=skip_if_exists,
                    reader=reader,
                    auth=auth,
                )
            if topics:
                await self.ainsert(
                    name=name,
                    description=description,
                    topics=topics,
                    metadata=metadata,
                    include=include,
                    exclude=exclude,
                    upsert=upsert,
                    skip_if_exists=skip_if_exists,
                    reader=reader,
                    auth=auth,
                )

            if remote_content:
                await self.ainsert(
                    name=name,
                    metadata=metadata,
                    description=description,
                    remote_content=remote_content,
                    upsert=upsert,
                    skip_if_exists=skip_if_exists,
                    reader=reader,
                    auth=auth,
                )

        else:
            raise ValueError("Invalid usage of insert_many.")

    @overload
    def insert_many(self, contents: List[ContentDict]) -> None: ...

    @overload
    def insert_many(
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

    def insert_many(self, *args, **kwargs) -> None:
        """
        Synchronously insert multiple content items into the knowledge base.

        Supports two usage patterns:
        1. Pass a list of content dictionaries as first argument
        2. Pass keyword arguments with paths, urls, metadata, etc.

        Args:
            contents: List of content dictionaries (when used as first overload)
            paths: Optional list of file paths to load content from
            urls: Optional list of URLs to load content from
            metadata: Optional metadata dictionary to apply to all content
            topics: Optional list of topics to insert
            text_contents: Optional list of text content strings to insert
            reader: Optional reader to use for processing content
            include: Optional list of file patterns to include
            exclude: Optional list of file patterns to exclude
            upsert: Whether to update existing content if it already exists (only used when skip_if_exists=False)
            skip_if_exists: Whether to skip inserting content if it already exists (default: True)
            remote_content: Optional remote content (S3, GCS, etc.) to insert
        """
        if args and isinstance(args[0], list):
            arguments = args[0]
            upsert = kwargs.get("upsert", True)
            skip_if_exists = kwargs.get("skip_if_exists", False)
            for argument in arguments:
                self.insert(
                    name=argument.get("name"),
                    description=argument.get("description"),
                    path=argument.get("path"),
                    url=argument.get("url"),
                    metadata=argument.get("metadata"),
                    topics=argument.get("topics"),
                    text_content=argument.get("text_content"),
                    reader=argument.get("reader"),
                    include=argument.get("include"),
                    exclude=argument.get("exclude"),
                    upsert=argument.get("upsert", upsert),
                    skip_if_exists=argument.get("skip_if_exists", skip_if_exists),
                    remote_content=argument.get("remote_content", None),
                    auth=argument.get("auth"),
                )

        elif kwargs:
            name = kwargs.get("name", [])
            metadata = kwargs.get("metadata", {})
            description = kwargs.get("description", [])
            topics = kwargs.get("topics", [])
            reader = kwargs.get("reader", None)
            paths = kwargs.get("paths", [])
            urls = kwargs.get("urls", [])
            text_contents = kwargs.get("text_contents", [])
            include = kwargs.get("include")
            exclude = kwargs.get("exclude")
            upsert = kwargs.get("upsert", True)
            skip_if_exists = kwargs.get("skip_if_exists", False)
            remote_content = kwargs.get("remote_content", None)
            auth = kwargs.get("auth")
            for path in paths:
                self.insert(
                    name=name,
                    description=description,
                    path=path,
                    metadata=metadata,
                    include=include,
                    exclude=exclude,
                    upsert=upsert,
                    skip_if_exists=skip_if_exists,
                    reader=reader,
                    auth=auth,
                )
            for url in urls:
                self.insert(
                    name=name,
                    description=description,
                    url=url,
                    metadata=metadata,
                    include=include,
                    exclude=exclude,
                    upsert=upsert,
                    skip_if_exists=skip_if_exists,
                    reader=reader,
                    auth=auth,
                )
            for i, text_content in enumerate(text_contents):
                content_name = f"{name}_{i}" if name else f"text_content_{i}"
                log_debug(f"Adding text content: {content_name}")
                self.insert(
                    name=content_name,
                    description=description,
                    text_content=text_content,
                    metadata=metadata,
                    include=include,
                    exclude=exclude,
                    upsert=upsert,
                    skip_if_exists=skip_if_exists,
                    reader=reader,
                    auth=auth,
                )
            if topics:
                self.insert(
                    name=name,
                    description=description,
                    topics=topics,
                    metadata=metadata,
                    include=include,
                    exclude=exclude,
                    upsert=upsert,
                    skip_if_exists=skip_if_exists,
                    reader=reader,
                    auth=auth,
                )

            if remote_content:
                self.insert(
                    name=name,
                    metadata=metadata,
                    description=description,
                    remote_content=remote_content,
                    upsert=upsert,
                    skip_if_exists=skip_if_exists,
                    reader=reader,
                    auth=auth,
                )

        else:
            raise ValueError("Invalid usage of insert_many.")
