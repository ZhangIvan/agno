"""Page image upload, signing, resolution, and cleanup methods for the Knowledge class.

These methods handle the lifecycle of page images:
- Upload to OSS/cloud storage (sync/async)
- Cleanup local cache files
- Sign URLs for time-limited access
- Strip signatures for logging
- Upload original files
- Resolve page images by page number
- JIT upload local paths to URLs
- Verify URL accessibility
- Collect page images for retrieved documents
"""

import asyncio
import os
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from agno.knowledge.content import Content
from agno.knowledge.document import Document
from agno.utils.log import log_debug, log_warning


class _KnowledgePageImageMixin:
    """Page image upload, signing, resolution, and cleanup."""

    # Local-path fields that must never appear in returned references
    _LOCAL_META_FIELDS = ("page_image_path", "pages_cache_dir", "pages_cache_url")

    # ========================================================================
    # Page Image Upload
    # ========================================================================

    def _upload_page_images(self, docs: List[Document]) -> Tuple[List[Document], List[str]]:
        """Upload page image PNGs to OSS and annotate docs with remote URLs.

        OSS key: ``{content_id}/page_{N}.png`` (storage backend prepends key_prefix).

        Local path handling:
        - ``page_image_path`` and ``pages_cache_dir`` are removed from ``meta_data``
          immediately so they are never persisted to the vector store.
        - The local path is saved in ``doc.local_embed_path`` (a transient, non-persisted
          Document field) so that ``embed()`` can still use it during ``vector_db.insert()``.
        - The caller should invoke ``_cleanup_local_page_images()`` after insert to
          delete the local files and clear ``local_embed_path``.

        Returns:
            (docs, local_paths) where local_paths are PNG files to delete after insert.
        """
        if not self.page_image_storage:
            return docs, []

        page_url_map: Dict[int, str] = {}  # page_num -> image_url
        local_paths: List[str] = []

        # Collect items to upload
        upload_items: List[
            Tuple[Document, str, str, str, bool]
        ] = []  # (doc, local_path, object_key, page_num, is_cache)
        for doc in docs:
            local_path = doc.meta_data.get("page_image_path")
            if not local_path:
                continue
            page_num = doc.meta_data.get("page_number")
            if page_num is None:
                continue
            is_cache_file = "pages_cache_dir" in doc.meta_data
            content_id = doc.content_id or doc.name or ""
            img_suffix = os.path.splitext(local_path)[1] or ".webp"
            object_key = f"{content_id}/page_{page_num}{img_suffix}"
            upload_items.append((doc, local_path, object_key, page_num, is_cache_file))

        # Upload with retry (parallelized via ThreadPoolExecutor)
        def _upload_one(
            item: Tuple[Document, str, str, str, bool],
        ) -> Tuple[Document, str, str, Optional[str], bool]:
            doc, local_path, object_key, page_num, is_cache = item
            url: Optional[str] = None
            for attempt in range(self.upload_max_retries + 1):
                try:
                    url = self.page_image_storage.upload(local_path, object_key)
                    break
                except Exception as e:
                    if attempt == self.upload_max_retries:
                        log_warning(
                            f"PageImageStorage.upload failed after {self.upload_max_retries} retries "
                            f"for {local_path}: {e}"
                        )
                    else:
                        import time as _time

                        delay = min(self.upload_retry_base_delay * (2**attempt), 10)
                        log_warning(f"Upload retry {attempt + 1}/{self.upload_max_retries} for {local_path}: {e}")
                        _time.sleep(delay)
            return doc, local_path, page_num, url, is_cache

        if upload_items:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(max_workers=self.upload_concurrency) as executor:
                futures = {executor.submit(_upload_one, item): item for item in upload_items}
                for future in as_completed(futures):
                    doc, local_path, page_num, url, is_cache = future.result()
                    if url:
                        doc.meta_data["page_image_url"] = url
                        doc.local_embed_path = local_path
                        doc.meta_data.pop("page_image_path", None)
                        doc.meta_data.pop("pages_cache_dir", None)
                        doc.meta_data.pop("pages_cache_url", None)
                        page_url_map[page_num] = url
                        if is_cache:
                            local_paths.append(local_path)

        # Phase 2: propagate url info to text_chunk docs with matching page_number
        if page_url_map:
            for doc in docs:
                if doc.meta_data.get("doc_type") == "text_chunk":
                    page_num = doc.meta_data.get("page_number")
                    if page_num in page_url_map:
                        doc.meta_data["page_image_url"] = page_url_map[page_num]
                        doc.meta_data.pop("page_image_path", None)
                        doc.meta_data.pop("pages_cache_dir", None)
                        doc.meta_data.pop("pages_cache_url", None)

        return docs, local_paths

    async def _async_upload_page_images(self, docs: List[Document]) -> Tuple[List[Document], List[str]]:
        """Async version of ``_upload_page_images``.

        Uses concurrent uploads with a semaphore to limit parallelism and
        exponential-backoff retry for transient failures.
        """
        import asyncio

        if not self.page_image_storage:
            return docs, []

        # Collect upload tasks
        upload_items: List[Tuple[Document, str, int, bool, str]] = []
        for doc in docs:
            local_path = doc.meta_data.get("page_image_path")
            if not local_path:
                continue
            page_num = doc.meta_data.get("page_number")
            if page_num is None:
                continue
            is_cache_file = "pages_cache_dir" in doc.meta_data
            content_id = doc.content_id or doc.name or ""
            img_suffix = os.path.splitext(local_path)[1] or ".webp"
            object_key = f"{content_id}/page_{page_num}{img_suffix}"
            upload_items.append((doc, local_path, page_num, is_cache_file, object_key))

        if not upload_items:
            return docs, []

        semaphore = asyncio.Semaphore(self.upload_concurrency)
        max_retries = self.upload_max_retries
        base_delay = self.upload_retry_base_delay
        storage = self.page_image_storage

        async def _upload_one(
            doc: Document, local_path: str, page_num: int, is_cache_file: bool, object_key: str
        ) -> Optional[Tuple[Document, int, str, Optional[str]]]:
            async with semaphore:
                for attempt in range(max_retries + 1):
                    try:
                        url = await storage.async_upload(local_path, object_key)
                        return (doc, page_num, url, local_path if is_cache_file else None)
                    except Exception as e:
                        if attempt == max_retries:
                            log_warning(
                                f"PageImageStorage.async_upload failed after {max_retries} retries "
                                f"for {local_path}: {e}"
                            )
                            return None
                        delay = min(base_delay * (2**attempt), 10)
                        log_warning(f"Upload retry {attempt + 1}/{max_retries} for {local_path}: {e}")
                        await asyncio.sleep(delay)
            return None  # pragma: no cover

        # Phase 1: concurrent uploads with retry
        results = await asyncio.gather(*[_upload_one(doc, lp, pn, ic, ok) for doc, lp, pn, ic, ok in upload_items])

        page_url_map: Dict[int, str] = {}
        local_paths: List[str] = []
        for result in results:
            if result is None:
                continue
            doc, page_num, url, cache_path = result
            doc.meta_data["page_image_url"] = url
            doc.local_embed_path = doc.meta_data.get("page_image_path")
            doc.meta_data.pop("page_image_path", None)
            doc.meta_data.pop("pages_cache_dir", None)
            doc.meta_data.pop("pages_cache_url", None)
            page_url_map[page_num] = url
            if cache_path:
                local_paths.append(cache_path)

        # Phase 2: propagate url info to text_chunk docs with matching page_number
        if page_url_map:
            for doc in docs:
                if doc.meta_data.get("doc_type") == "text_chunk":
                    page_num = doc.meta_data.get("page_number")
                    if page_num in page_url_map:
                        doc.meta_data["page_image_url"] = page_url_map[page_num]
                        doc.meta_data.pop("page_image_path", None)
                        doc.meta_data.pop("pages_cache_dir", None)
                        doc.meta_data.pop("pages_cache_url", None)

        return docs, local_paths

    # ========================================================================
    # Cleanup
    # ========================================================================

    def _cleanup_local_page_images(self, docs: List[Document], local_paths: List[str]) -> None:
        """Delete local page image files after vector DB insert.

        Removes the files listed in ``local_paths``, then tries to remove their
        parent directory if it becomes empty (handles dedicated cache directories
        created for PDF/PPTX page image conversion).
        Also clears the transient ``local_embed_path`` field on each doc.
        """
        parent_dirs: set = set()
        for local_path in local_paths:
            try:
                os.unlink(local_path)
                parent_dirs.add(os.path.dirname(local_path))
            except OSError as e:
                log_warning(f"Could not delete local page cache {local_path}: {e}")

        for parent_dir in parent_dirs:
            try:
                os.rmdir(parent_dir)
            except OSError:
                pass  # Not empty or already gone — ignore

        for doc in docs:
            doc.local_embed_path = None

    async def _async_cleanup_local_page_images(self, docs: List[Document], local_paths: List[str]) -> None:
        """Async version of :meth:`_cleanup_local_page_images`."""
        import asyncio

        parent_dirs: set = set()
        for local_path in local_paths:
            try:
                await asyncio.to_thread(os.unlink, local_path)
                parent_dirs.add(os.path.dirname(local_path))
            except OSError as e:
                log_warning(f"Could not delete local page cache {local_path}: {e}")

        for parent_dir in parent_dirs:
            try:
                await asyncio.to_thread(os.rmdir, parent_dir)
            except OSError:
                pass

        for doc in docs:
            doc.local_embed_path = None

    # ========================================================================
    # Reference dict helpers
    # ========================================================================

    def _doc_to_reference_dict(self, doc: Document) -> Dict[str, Any]:
        """Build a reference dict from a retrieved Document suitable for returning to callers.

        - Strips any local file path fields that may have been stored by older code.
        - Signs ``page_image_url`` and ``file_url`` with the configured storage backend
          so callers receive time-limited URLs that work for private buckets.
        """
        result = doc.to_dict()
        meta = result.get("meta_data")
        if not isinstance(meta, dict):
            return result

        # Work on a copy so the in-memory Document is not mutated
        meta = dict(meta)
        result["meta_data"] = meta

        # Strip local path fields (backward compat for already-stored data)
        for field_name in self._LOCAL_META_FIELDS:
            meta.pop(field_name, None)

        # Sign OSS URLs if storage is configured
        if self.page_image_storage:
            for url_field in ("page_image_url", "file_url"):
                url = meta.get(url_field)
                if url:
                    try:
                        meta[url_field] = self.page_image_storage.sign_url(url, expires=self.url_signature_expires)
                    except Exception as e:
                        log_warning(f"sign_url failed for {url_field}={self._strip_url_signature(url)}: {e}")

        return result

    async def _async_doc_to_reference_dict(self, doc: Document) -> Dict[str, Any]:
        """Async version of ``_doc_to_reference_dict``."""
        result = doc.to_dict()
        meta = result.get("meta_data")
        if not isinstance(meta, dict):
            return result

        meta = dict(meta)
        result["meta_data"] = meta

        for field_name in self._LOCAL_META_FIELDS:
            meta.pop(field_name, None)

        if self.page_image_storage:
            for url_field in ("page_image_url", "file_url"):
                url = meta.get(url_field)
                if url:
                    try:
                        meta[url_field] = await self.page_image_storage.async_sign_url(
                            url, expires=self.url_signature_expires
                        )
                    except Exception as e:
                        log_warning(f"async_sign_url failed for {url_field}={self._strip_url_signature(url)}: {e}")

        return result

    def _sign_reference_urls(self, references: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sign storage URLs in reference dicts for time-limited access.

        Takes a list of reference dicts (as returned by ``_doc_to_reference_dict``)
        and returns a new list with ``page_image_url`` and ``file_url`` fields signed.
        The input list is not mutated.
        """
        if not self.page_image_storage:
            return references
        signed: List[Dict[str, Any]] = []
        for ref in references:
            ref = dict(ref)
            meta = ref.get("meta_data")
            if isinstance(meta, dict):
                meta = dict(meta)
                ref["meta_data"] = meta
                for url_field in ("page_image_url", "file_url"):
                    url = meta.get(url_field)
                    if url:
                        try:
                            meta[url_field] = self.page_image_storage.sign_url(url, expires=self.url_signature_expires)
                        except Exception as e:
                            log_warning(f"sign_url failed for {url_field}={self._strip_url_signature(url)}: {e}")
            signed.append(ref)
        return signed

    async def _async_sign_reference_urls(self, references: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Async version of ``_sign_reference_urls``.

        Signs all storage URLs in parallel using ``asyncio.gather`` for
        better throughput when multiple references need signing.
        """
        import asyncio

        if not self.page_image_storage:
            return references

        # Prepare shallow copies and collect signing tasks
        ref_copies: List[Dict[str, Any]] = []
        sign_tasks: List[Tuple[int, str, str]] = []  # (ref_idx, url_field, original_url)

        for i, ref in enumerate(references):
            ref = dict(ref)
            meta = ref.get("meta_data")
            if isinstance(meta, dict):
                meta = dict(meta)
                ref["meta_data"] = meta
                for url_field in ("page_image_url", "file_url"):
                    url = meta.get(url_field)
                    if url:
                        sign_tasks.append((i, url_field, url))
            ref_copies.append(ref)

        if not sign_tasks:
            return ref_copies

        # Execute all sign_url calls concurrently
        async def _sign_one(idx: int, url_field: str, url: str) -> Tuple[int, str, Optional[str]]:
            try:
                signed_url = await self.page_image_storage.async_sign_url(url, expires=self.url_signature_expires)
                return (idx, url_field, signed_url)
            except Exception as e:
                log_warning(f"async_sign_url failed for {url_field}={self._strip_url_signature(url)}: {e}")
                return (idx, url_field, None)

        results = await asyncio.gather(*[_sign_one(*task) for task in sign_tasks])

        # Apply signed URLs back to copies
        for idx, url_field, signed_url in results:
            if signed_url is not None:
                meta = ref_copies[idx].get("meta_data")
                if isinstance(meta, dict):
                    meta[url_field] = signed_url

        return ref_copies

    # ========================================================================
    # URL signature stripping
    # ========================================================================

    @staticmethod
    def _strip_url_signature(url: str) -> str:
        """Strip query-string signature from an OSS/cloud storage URL.

        Returns the base URL without query parameters.  Non-http URLs and
        URLs without query strings are returned unchanged.
        """
        if not url or not url.startswith(("http://", "https://")):
            return url
        return url.split("?")[0]

    @staticmethod
    def _strip_reference_url_signatures(
        references: List[Any],  # List[MessageReferences]
    ) -> List[Any]:  # List[MessageReferences]
        """Return a copy of *references* with OSS URL signatures stripped.

        Each ``page_image_url`` and ``file_url`` in ``meta_data`` is reduced to
        its base URL (query string removed).  The original objects are not mutated.
        """
        from agno.models.message import MessageReferences as MR

        stripped: List[MR] = []
        for ref_group in references:
            if not ref_group.references:
                stripped.append(ref_group)
                continue
            new_refs = []
            for ref in ref_group.references:
                if not isinstance(ref, dict):
                    new_refs.append(ref)
                    continue
                meta = ref.get("meta_data")
                if not isinstance(meta, dict):
                    new_refs.append(ref)
                    continue
                needs_strip = False
                for url_field in ("page_image_url", "file_url"):
                    url = meta.get(url_field)
                    if url and "?" in url:
                        needs_strip = True
                        break
                if not needs_strip:
                    new_refs.append(ref)
                    continue
                ref = dict(ref)
                meta = dict(meta)
                ref["meta_data"] = meta
                for url_field in ("page_image_url", "file_url"):
                    url = meta.get(url_field)
                    if url:
                        meta[url_field] = _KnowledgePageImageMixin._strip_url_signature(url)
                new_refs.append(ref)
            stripped.append(MR(query=ref_group.query, references=new_refs, time=ref_group.time))
        return stripped

    # ========================================================================
    # Original file upload
    # ========================================================================

    def _upload_original_file(
        self,
        content: Content,
        file_source: Union[Path, BytesIO],
        docs: List[Document],
    ) -> List[Document]:
        """Upload the original file to OSS and annotate all docs with ``file_url``.

        OSS key: ``{content_id}/{filename}`` (storage backend prepends key_prefix).
        For a :class:`~pathlib.Path` source the user's local file is NOT deleted.
        For a :class:`~io.BytesIO` source a temp file is written, uploaded, then
        deleted so no local copy of the original is kept.
        """
        from agno.knowledge.reader.utils import temp_file_from_bytesio

        if not self.page_image_storage:
            return docs

        content_id = content.id or ""
        filename = content.name or "file"
        object_key = f"{content_id}/{filename}"
        try:
            suffix = Path(filename).suffix or ".bin"
            with temp_file_from_bytesio(file_source, suffix) as tmp_path:
                url = self.page_image_storage.upload(str(tmp_path), object_key)
            for doc in docs:
                doc.meta_data["file_url"] = url
        except Exception as e:
            log_warning(f"Failed to upload original file {filename}: {e}")
        return docs

    async def _async_upload_original_file(
        self,
        content: Content,
        file_source: Union[Path, BytesIO],
        docs: List[Document],
    ) -> List[Document]:
        """Async version of :meth:`_upload_original_file`."""
        from agno.knowledge.reader.utils import temp_file_from_bytesio

        if not self.page_image_storage:
            return docs

        content_id = content.id or ""
        filename = content.name or "file"
        object_key = f"{content_id}/{filename}"
        try:
            suffix = Path(filename).suffix or ".bin"
            with temp_file_from_bytesio(file_source, suffix) as tmp_path:
                url = await self.page_image_storage.async_upload(str(tmp_path), object_key)
            for doc in docs:
                doc.meta_data["file_url"] = url
        except Exception as e:
            log_warning(f"Failed to upload original file {filename}: {e}")
        return docs

    # ========================================================================
    # Page image resolution
    # ========================================================================

    def _resolve_page_image(self, doc: Document, page_num: int) -> Optional[str]:
        """Resolve a page image reference for the given physical page number.

        Returns a signed OSS URL when ``page_image_storage`` is configured,
        or a local file path otherwise.  Returns ``None`` if the image cannot
        be found.
        """
        from pathlib import Path

        storage = self.page_image_storage

        # --- Direct match (this doc's own page) ---
        if doc.meta_data.get("page_number") == page_num:
            # 1. OSS: sign the stored URL
            if storage:
                url = doc.meta_data.get("page_image_url")
                if url:
                    try:
                        return storage.sign_url(url, expires=self.url_signature_expires)
                    except Exception as e:
                        log_warning(f"sign_url failed for {self._strip_url_signature(url)}: {e}")
            # 2. Local: return path if file still exists
            path = doc.meta_data.get("page_image_path")
            if path and Path(path).is_file():
                return path

        # --- Adjacent page (sliding window) ---
        # 3. OSS: derive cache URL from the doc's own page_image_url and sign it
        if storage:
            own_url = doc.meta_data.get("page_image_url")
            if own_url:
                # Derive the cache directory prefix from the stored URL, e.g.:
                #   "https://bucket/prefix/content_id/page_3.png"
                #   -> "https://bucket/prefix/content_id/"
                cache_url = own_url.rsplit("/", 1)[0] + "/"
                adj_url = f"{cache_url}page_{page_num}.png"
                try:
                    return storage.sign_url(adj_url, expires=self.url_signature_expires)
                except Exception as e:
                    log_warning(f"sign_url failed for {self._strip_url_signature(adj_url)}: {e}")

        # 4. Local: look up cache directory
        doc_name = doc.name or (doc.content_id or "").split("_page_")[0]
        if not doc_name:
            return None

        # Prefer the custom cache dir stored in metadata, then fall back to default
        cache_base = doc.meta_data.get("pages_cache_dir")
        if cache_base:
            cache_path = Path(cache_base) / f"page_{page_num}.png"
        else:
            cache_path = Path.home() / ".agno" / "page_cache" / doc_name / f"page_{page_num}.png"

        if cache_path.exists():
            return str(cache_path)
        return None

    # Keep old name as an alias for backwards compatibility
    def _resolve_page_image_path(self, doc: Document, page_num: int) -> Optional[str]:
        return self._resolve_page_image(doc, page_num)

    # ========================================================================
    # URL accessibility check
    # ========================================================================

    def _check_url_accessible(self, url: str) -> bool:
        """Perform a lightweight HEAD request to verify a URL is reachable.

        Only checks http/https URLs.  Returns True for local paths, base64, etc.
        """
        if not url.startswith(("http://", "https://")):
            return True
        try:
            import httpx

            with httpx.Client(timeout=self.verify_image_url_timeout) as client:
                resp = client.head(url, follow_redirects=True)
                return resp.status_code < 400
        except Exception:
            return False

    async def _async_check_url_accessible(self, url: str) -> bool:
        """Async version of ``_check_url_accessible``."""
        if not url.startswith(("http://", "https://")):
            return True
        try:
            import httpx

            async with httpx.AsyncClient(timeout=self.verify_image_url_timeout) as client:
                resp = await client.head(url, follow_redirects=True)
                return resp.status_code < 400
        except Exception:
            return False

    # ========================================================================
    # JIT upload: prefer URL over local path
    # ========================================================================

    def _prefer_url_over_local(self, doc: Document, page_num: int, resolved: str) -> str:
        """If *resolved* is a local file path and ``page_image_storage`` is configured,
        upload the file on-the-fly and return a signed URL.

        This avoids sending large base64-encoded images to multimodal LLMs when a
        cloud-storage backend is available.  Returns the original *resolved* string
        unchanged when no storage is configured or the upload fails.
        """
        if resolved.startswith("http") or not self.page_image_storage:
            return resolved

        if not Path(resolved).is_file():
            return resolved

        storage = self.page_image_storage
        content_id = doc.content_id or doc.name or ""
        img_suffix = os.path.splitext(resolved)[1] or ".png"
        object_key = f"{content_id}/page_{page_num}{img_suffix}"

        try:
            url = storage.upload(resolved, object_key)
            if url:
                signed = storage.sign_url(url, expires=self.url_signature_expires)
                if signed:
                    log_debug("JIT-uploaded page image (signed URL generated)")
                    return signed
        except Exception as e:
            log_warning(f"JIT upload failed for page {page_num}: {e}")

        return resolved

    async def _async_prefer_url_over_local(self, doc: Document, page_num: int, resolved: str) -> str:
        """Async version of :meth:`_prefer_url_over_local`."""
        if resolved.startswith("http") or not self.page_image_storage:
            return resolved

        if not await asyncio.to_thread(Path(resolved).is_file):
            return resolved

        storage = self.page_image_storage
        content_id = doc.content_id or doc.name or ""
        img_suffix = os.path.splitext(resolved)[1] or ".png"
        object_key = f"{content_id}/page_{page_num}{img_suffix}"

        try:
            url = await storage.async_upload(resolved, object_key)
            if url:
                signed = await storage.async_sign_url(url, expires=self.url_signature_expires)
                if signed:
                    log_debug("JIT-uploaded page image (signed URL generated)")
                    return signed
        except Exception as e:
            log_warning(f"Async JIT upload failed for page {page_num}: {e}")

        return resolved

    # ========================================================================
    # Page image collection for retrieval
    # ========================================================================

    def _get_page_images_for_docs(self, docs: List[Document]) -> List[Any]:
        """Collect page images for retrieved documents.

        For each matched document:
        - If it is a page_image document, include that exact page.
        - If it is a text chunk, include pages [page-window, ..., page+window].

        Deduplicates by (doc_identifier, page_number) and caps at max_retrieval_images.

        When ``page_image_storage`` is configured and a local file path is resolved,
        the image is uploaded on-the-fly so that a signed URL is sent to the LLM
        instead of embedding the file as base64 (which produces a large request body).

        Returns:
            List of agno.media.Image objects.
        """
        from agno.media import Image

        seen: set = set()
        image_refs: List[tuple] = []  # (doc_id, page_num, image_path_or_url)

        # Clamp config values to safe bounds
        window = max(0, self.image_window_size)
        max_images = max(1, self.max_retrieval_images)
        for doc in docs:
            # Safely coerce page_number to a positive int
            raw_page = doc.meta_data.get("page_number")
            try:
                page_num: Optional[int] = int(raw_page) if raw_page is not None else None
            except (TypeError, ValueError):
                page_num = None
            if page_num is not None and page_num <= 0:
                page_num = None

            # Safely coerce total_pages
            raw_total = doc.meta_data.get("total_pages")
            try:
                total: int = int(raw_total) if raw_total is not None else 9999
            except (TypeError, ValueError):
                total = 9999
            if total <= 0:
                total = 9999

            doc_id = doc.content_id or doc.name or ""
            if doc.meta_data.get("doc_type") == "page_image":
                # Direct image hit — include exactly this page
                pages_to_add = [page_num] if page_num is not None else []
            elif page_num is not None:
                # Text chunk — sliding window
                pages_to_add = list(
                    range(
                        max(1, page_num - window),
                        min(total, page_num + window) + 1,
                    )
                )
            else:
                pages_to_add = []

            for p in pages_to_add:
                if len(image_refs) >= max_images:
                    break
                key = (doc_id, p)
                if key not in seen:
                    resolved = self._resolve_page_image(doc, p)
                    if resolved:
                        # Prefer URL over local path: upload on-the-fly if storage
                        # is available but we only got a local file path.
                        resolved = self._prefer_url_over_local(doc, p, resolved)
                        if self.verify_image_urls and resolved.startswith("http"):
                            if not self._check_url_accessible(resolved):
                                log_warning(f"Skipping unreachable image URL: {self._strip_url_signature(resolved)}")
                                continue
                        seen.add(key)
                        image_refs.append((doc_id, p, resolved))

        # Sort by (doc_id, page_number) for consistent ordering
        return [Image(url=r) if r.startswith("http") else Image(filepath=r) for _, _, r in image_refs[:max_images]]
