import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse, unquote

from agno.knowledge.reader.base import Reader
from agno.knowledge.reader.reader_factory import ReaderFactory
from agno.knowledge.types import ContentType
from agno.utils.log import log_debug
from agno.utils.media import get_image_type

RESERVED_AGNO_KEY = "_ag_os"


def multi_unquote(s: str, max_rounds: int = 10) -> str:
    """
    循环调用 unquote，直到字符串不再变化（或达到最大轮数）
    """
    prev = None
    current = s
    _round = 0
    while current != prev and _round < max_rounds:
        prev = current
        current = unquote(current)
        _round += 1
    return current


def format_image_meta(meta) -> str:
    """Format metadata dict into a concise Chinese string for image source descriptions.

    Returns empty string if *meta* is falsy, otherwise a JSON dump prefixed with
    ``", 附加信息: "``.
    """
    if not meta:
        return ""
    return f", 附加信息: {json.dumps(meta, ensure_ascii=False)}"


def build_page_image_tool_result(
    image_results: List[Tuple[Any, str, int, Dict[str, Any]]],
) -> Any:
    """Build a ToolResult from page image results.

    Args:
        image_results: List of (Image, doc_name, page_number, meta_data) tuples
            as returned by ``_get_page_images_for_docs``.

    Returns:
        A ``ToolResult`` with the image list and a formatted content string,
        or ``None`` if *image_results* is empty.
    """
    if not image_results:
        return None

    from agno.tools.function import ToolResult

    images = [img for img, _, _, _ in image_results]
    source_info = ". ".join(
        f"* 图片{os.path.basename(urlparse(img.url or str(img.filepath or '')).path)}(来源: {name}, 第{page}页)"
        for img, name, page, meta in image_results
    )
    return ToolResult(
        content=(
            "The following images are relevant document pages from the knowledge base. "
            f"Read the content in these images to answer the user's question.\n [{source_info}]"
        ),
        images=images,
    )


def merge_user_metadata(
    existing: Optional[Dict[str, Any]],
    incoming: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Deep-merge two metadata dicts, preserving the ``_agno`` sub-key from both sides.

    Top-level keys from *incoming* overwrite those in *existing* (except ``_agno``).
    Keys inside ``_agno`` are merged individually so that info added
    after initial source info is not lost.
    """
    if not existing:
        return incoming
    if not incoming:
        return existing

    merged = dict(existing)
    for key, value in incoming.items():
        if key == RESERVED_AGNO_KEY:
            old_agno = merged.get(RESERVED_AGNO_KEY, {}) or {}
            new_agno = value if isinstance(value, dict) else {}
            merged[RESERVED_AGNO_KEY] = {**old_agno, **new_agno}
        else:
            merged[key] = value
    return merged


def set_agno_metadata(
    metadata: Optional[Dict[str, Any]],
    key: str,
    value: Any,
) -> Dict[str, Any]:
    """Set a key under the reserved ``_agno`` namespace in metadata."""
    if metadata is None:
        metadata = {}
    agno_meta = metadata.get(RESERVED_AGNO_KEY, {}) or {}
    agno_meta[key] = value
    metadata[RESERVED_AGNO_KEY] = agno_meta
    return metadata


def get_agno_metadata(
    metadata: Optional[Dict[str, Any]],
    key: str,
) -> Any:
    """Get a key from the reserved ``_agno`` namespace in metadata."""
    if not metadata:
        return None
    agno_meta = metadata.get(RESERVED_AGNO_KEY)
    if not isinstance(agno_meta, dict):
        return None
    return agno_meta.get(key)


def strip_agno_metadata(
    metadata: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Return a copy of *metadata* without the reserved ``_agno`` key.

    Useful before sending metadata to the vector DB where only
    user-defined fields should be searchable.
    """
    if not metadata:
        return metadata
    return {k: v for k, v in metadata.items() if k != RESERVED_AGNO_KEY}


def _get_chunker_class(strategy_type):
    """Get the chunker class for a given strategy type without instantiation."""
    from agno.knowledge.chunking.strategy import ChunkingStrategyType

    # Map strategy types to their corresponding classes
    strategy_class_mapping = {
        ChunkingStrategyType.AGENTIC_CHUNKER: lambda: _import_class(
            "agno.knowledge.chunking.agentic", "AgenticChunking"
        ),
        ChunkingStrategyType.CODE_CHUNKER: lambda: _import_class("agno.knowledge.chunking.code", "CodeChunking"),
        ChunkingStrategyType.DOCUMENT_CHUNKER: lambda: _import_class(
            "agno.knowledge.chunking.document", "DocumentChunking"
        ),
        ChunkingStrategyType.RECURSIVE_CHUNKER: lambda: _import_class(
            "agno.knowledge.chunking.recursive", "RecursiveChunking"
        ),
        ChunkingStrategyType.SEMANTIC_CHUNKER: lambda: _import_class(
            "agno.knowledge.chunking.semantic", "SemanticChunking"
        ),
        ChunkingStrategyType.FIXED_SIZE_CHUNKER: lambda: _import_class(
            "agno.knowledge.chunking.fixed", "FixedSizeChunking"
        ),
        ChunkingStrategyType.ROW_CHUNKER: lambda: _import_class("agno.knowledge.chunking.row", "RowChunking"),
        ChunkingStrategyType.MARKDOWN_CHUNKER: lambda: _import_class(
            "agno.knowledge.chunking.markdown", "MarkdownChunking"
        ),
    }

    if strategy_type not in strategy_class_mapping:
        raise ValueError(f"Unknown strategy type: {strategy_type}")

    return strategy_class_mapping[strategy_type]()


def _import_class(module_name: str, class_name: str):
    """Dynamically import a class from a module."""
    import importlib

    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def get_reader_info(reader_key: str) -> Dict:
    """Get information about a reader without instantiating it.

    Uses class methods and static metadata from ReaderFactory to avoid
    the overhead of creating reader instances.
    """
    try:
        # Get the reader CLASS without instantiation
        reader_class = ReaderFactory.get_reader_class(reader_key)

        # Get metadata from static registry (no instantiation needed)
        metadata = ReaderFactory.READER_METADATA.get(reader_key, {})

        # Call class methods directly (no instance needed)
        supported_strategies = reader_class.get_supported_chunking_strategies()  # type: ignore[attr-defined]
        supported_content_types = reader_class.get_supported_content_types()  # type: ignore[attr-defined]

        return {
            "id": reader_key,
            "name": metadata.get("name", reader_class.__name__),
            "description": metadata.get("description", f"{reader_class.__name__} reader"),
            "chunking_strategies": [strategy.value for strategy in supported_strategies],
            "content_types": [ct.value for ct in supported_content_types],
        }
    except ImportError as e:
        # Skip readers with missing dependencies
        raise ValueError(f"Reader '{reader_key}' has missing dependencies: {str(e)}")
    except Exception as e:
        raise ValueError(f"Unknown reader: {reader_key}. Error: {str(e)}")


def get_reader_info_from_instance(reader: Reader, reader_id: str) -> Dict:
    """Get information about a reader instance."""
    try:
        reader_class = reader.__class__
        supported_strategies = reader_class.get_supported_chunking_strategies()
        supported_content_types = reader_class.get_supported_content_types()

        return {
            "id": reader_id,
            "name": getattr(reader, "name", reader_class.__name__),
            "description": getattr(reader, "description", f"Custom {reader_class.__name__}"),
            "chunking_strategies": [strategy.value for strategy in supported_strategies],
            "content_types": [ct.value for ct in supported_content_types],
        }
    except Exception as e:
        raise ValueError(f"Failed to get info for reader '{reader_id}': {str(e)}")


def get_all_readers_info(knowledge_instance: Optional[Any] = None) -> List[Dict]:
    """Get information about all available readers, including custom readers from a Knowledge instance.

    Custom readers are added first and take precedence over factory readers with the same ID.

    Args:
        knowledge_instance: Optional Knowledge instance to include custom readers from.

    Returns:
        List of reader info dictionaries (custom readers first, then factory readers).
    """
    readers_info = []
    seen_ids: set = set()

    # 1. Add custom readers FIRST (they take precedence over factory readers)
    if knowledge_instance is not None:
        custom_readers = knowledge_instance.get_readers()
        if isinstance(custom_readers, dict):
            for reader_id, reader in custom_readers.items():
                try:
                    reader_info = get_reader_info_from_instance(reader, reader_id)
                    readers_info.append(reader_info)
                    seen_ids.add(reader_id)
                except ValueError as e:
                    log_debug(f"Skipping custom reader '{reader_id}': {e}")
                    continue

    # 2. Add factory readers (skip if custom reader with same ID already exists)
    keys = ReaderFactory.get_all_reader_keys()
    for key in keys:
        if key in seen_ids:
            # Custom reader with this ID already added, skip factory version
            continue
        try:
            reader_info = get_reader_info(key)
            readers_info.append(reader_info)
        except ValueError as e:
            # Skip readers with missing dependencies or other issues
            log_debug(f"Skipping reader '{key}': {e}")
            continue

    return readers_info


def get_content_types_to_readers_mapping(knowledge_instance: Optional[Any] = None) -> Dict[str, List[str]]:
    """Get mapping of content types to list of reader IDs that support them.

    Args:
        knowledge_instance: Optional Knowledge instance to include custom readers from.

    Returns:
        Dictionary mapping content type strings (ContentType enum values) to list of reader IDs.
    """
    content_type_mapping: Dict[str, List[str]] = {}
    readers_info = get_all_readers_info(knowledge_instance)
    for reader_info in readers_info:
        reader_id = reader_info["id"]
        content_types = reader_info.get("content_types", [])

        for content_type in content_types:
            if content_type not in content_type_mapping:
                content_type_mapping[content_type] = []
            # Avoid duplicates
            if reader_id not in content_type_mapping[content_type]:
                content_type_mapping[content_type].append(reader_id)

    return content_type_mapping


def get_chunker_info(chunker_key: str) -> Dict:
    """Get information about a chunker without instantiating it."""
    try:
        # Use chunking strategies directly
        from agno.knowledge.chunking.strategy import ChunkingStrategyType

        try:
            # Use the chunker key directly as the strategy type value
            strategy_type = ChunkingStrategyType.from_string(chunker_key)

            # Get class directly without instantiation
            chunker_class = _get_chunker_class(strategy_type)

            # Extract class information
            class_name = chunker_class.__name__
            docstring = chunker_class.__doc__ or f"{class_name} chunking strategy"

            # Check class __init__ signature for chunk_size and overlap parameters
            metadata = {}
            import inspect

            try:
                sig = inspect.signature(chunker_class.__init__)
                param_names = set(sig.parameters.keys())

                # If class has chunk_size or max_chunk_size parameter, set default chunk_size
                if "chunk_size" in param_names or "max_chunk_size" in param_names:
                    metadata["chunk_size"] = 5000

                # If class has overlap parameter, set default overlap
                if "overlap" in param_names:
                    metadata["chunk_overlap"] = 0
            except Exception:
                # If we can't inspect, skip metadata
                pass

            return {
                "key": chunker_key,
                "class_name": class_name,
                "name": chunker_key,
                "description": docstring.strip(),
                "strategy_type": strategy_type.value,
                "metadata": metadata,
            }
        except ValueError:
            raise ValueError(f"Unknown chunker key: {chunker_key}")

    except ImportError as e:
        # Skip chunkers with missing dependencies
        raise ValueError(f"Chunker '{chunker_key}' has missing dependencies: {str(e)}")
    except Exception as e:
        raise ValueError(f"Unknown chunker: {chunker_key}. Error: {str(e)}")


def get_all_content_types() -> List[ContentType]:
    """Get all available content types as ContentType enums."""
    return list(ContentType)


def get_all_chunkers_info() -> List[Dict]:
    """Get information about all available chunkers."""
    chunkers_info = []

    from agno.knowledge.chunking.strategy import ChunkingStrategyType

    keys = [strategy_type.value for strategy_type in ChunkingStrategyType]

    for key in keys:
        try:
            chunker_info = get_chunker_info(key)
            chunkers_info.append(chunker_info)
        except ValueError as e:
            log_debug(f"Skipping chunker '{key}': {e}")
            continue
    return chunkers_info


# ==============================================================================
# Content-Type Mapping
# ==============================================================================

CONTENT_TYPE_MAP: Dict[str, str] = {
    # Images
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".bmp": "image/bmp",
    # Documents
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    # Data
    ".csv": "text/csv",
    ".json": "application/json",
    ".xml": "application/xml",
    ".yaml": "application/x-yaml",
    ".yml": "application/x-yaml",
    # Text
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    # Audio/Video
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".wav": "audio/wav",
    ".webm": "video/webm",
}


def get_content_type(file_path: str) -> str:
    """Get MIME content type by detecting file's actual content (magic bytes).

    Uses python-magic to detect the real file type from content, not just extension.
    Falls back to extension-based detection if python-magic is unavailable.

    Args:
        file_path: Path to the file.

    Returns:
        MIME type string, defaults to "application/octet-stream" if unknown.
    """
    # First, try to detect from file content using python-magic
    try:
        detected_type = _get_magic().from_file(file_path)
        if detected_type:
            return detected_type
    except ImportError:
        log_debug("python-magic not installed, falling back to extension-based detection")
    except Exception as e:
        log_debug(f"Failed to detect content type from file content: {e}")

    # Fallback: detect from file extension
    ext = Path(file_path).suffix.lower()
    return CONTENT_TYPE_MAP.get(ext, "application/octet-stream")


# Thread-local storage for python-magic — libmagic's magic_t handle is NOT
# safe to share across threads, so each thread gets its own Magic instance.
_magic_local = threading.local()


def _get_magic():
    """Return a thread-local ``magic.Magic(mime=True)`` instance."""
    if not hasattr(_magic_local, "instance"):
        import magic

        _magic_local.instance = magic.Magic(mime=True)
    return _magic_local.instance


def get_content_type_from_bytes(data: bytes) -> str:
    """Detect MIME content type from bytes using magic bytes.

    Caller should pass only the first 32KB of file content.
    Uses python-magic for accurate detection, falls back to heuristic checks.

    Returns:
        MIME type string, defaults to "application/octet-stream".
    """
    if not data:
        return "application/octet-stream"

    try:
        detected_type = _get_magic().from_buffer(data)
        if detected_type:
            return detected_type
    except ImportError:
        pass
    except Exception:
        pass

    return _detect_mime_from_magic_bytes(data)


def _detect_mime_from_magic_bytes(data: bytes) -> str:
    """Detect MIME type from well-known magic byte signatures.

    Covers common document, image, archive, and data formats used by the
    knowledge pipeline.  Returns ``application/octet-stream`` when no known
    signature matches.
    """
    if len(data) < 4:
        return "application/octet-stream"

    # PDF: %PDF
    if data[:4] == b"%PDF":
        return "application/pdf"

    # ZIP-based formats (docx, xlsx, pptx, odt, etc.)
    if data[:4] == b"PK\x03\x04":
        lower = data[:2000].lower()
        if b"content_types" in lower:
            if b"word/" in lower:
                return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if b"spreadsheet/" in lower or b"xl/" in lower:
                return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if b"presentation/" in lower or b"ppt/" in lower:
                return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        return "application/zip"

    # Images — reuse the shared magic-byte detector in utils/media.py
    img_type = get_image_type(data)
    if img_type:
        return f"image/{img_type}"

    # Audio/Video
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3"):
        return "audio/mpeg"
    if data[:4] == b"fLaC":
        return "audio/flac"
    # ftyp box: used by both HEIC/HEIF images and MP4/MOV video.
    # Check common HEIC brand identifiers before defaulting to video/mp4.
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"hevx", b"mif1"):
            return "image/heic"
        return "video/mp4"

    # Text-based heuristics
    if _looks_like_text(data[:8192]):
        text_sample = data[:4096]
        stripped = text_sample.lstrip()
        if stripped.startswith(b"<?xml") or stripped.startswith(b"<"):
            return "text/xml"
        if stripped.startswith(b"{") or stripped.startswith(b"["):
            return "application/json"
        return "text/plain"

    return "application/octet-stream"


_TEXT_ALLOWED_CONTROL_BYTES: frozenset = frozenset({10, 13, 9})  # \n, \r, \t


def _looks_like_text(data: bytes) -> bool:
    """Check whether *data* appears to be valid UTF-8 text."""
    try:
        data.decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return False
    control_chars = sum(data.count(b) for b in range(32) if b not in _TEXT_ALLOWED_CONTROL_BYTES)
    return control_chars < len(data) * 0.05


# MIME→canonical-extension lookup derived from CONTENT_TYPE_MAP.
# Used by detect_real_extension to map detected MIME back to an extension.
_MIME_TO_PRIMARY_EXT: Dict[str, str] = {}
for _ext, _mime in CONTENT_TYPE_MAP.items():
    if _mime not in _MIME_TO_PRIMARY_EXT:
        _MIME_TO_PRIMARY_EXT[_mime] = _ext


def detect_real_extension(data: bytes) -> str:
    """Detect real file extension from content bytes.

    Caller should pass at most the first 32KB of file content.
    Returns extension like ``".pdf"`` or empty string when detection fails.
    """
    if not data:
        return ""
    mime = get_content_type_from_bytes(data)
    return _MIME_TO_PRIMARY_EXT.get(mime, "")


def detect_real_extension_from_file(path: Union[str, Path]) -> str:
    """Detect real file extension by reading the first 2KB of a file."""
    with open(path, "rb") as f:
        return detect_real_extension(f.read(2048))


# Mapping from MIME type to ALL compatible file extensions.
# This is broader than the canonical mapping because magic bytes detect
# many formats as "text/plain" (e.g. .md, .csv, .json are all text/plain at
# the byte level even though they have distinct MIME types in CONTENT_TYPE_MAP).
# Used by validate_file_type_match for extension/content compatibility checks.
_MIME_TO_EXTENSIONS: Dict[str, set] = {
    "application/pdf": {".pdf"},
    "application/zip": {".zip"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {".xlsx"},
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": {".pptx"},
    "application/vnd.ms-excel": {".xls"},
    "application/msword": {".doc"},
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/gif": {".gif"},
    "image/webp": {".webp"},
    "image/heic": {".heic", ".heif"},
    "text/plain": {
        ".txt",
        ".md",
        ".markdown",
        ".csv",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".html",
        ".htm",
        ".css",
        ".js",
        ".py",
        ".ts",
        ".log",
    },
    "text/csv": {".csv"},
    "text/markdown": {".md", ".markdown"},
    "text/html": {".html", ".htm"},
    "application/json": {".json"},
    "application/xml": {".xml"},
    "text/xml": {".xml"},
    "audio/mpeg": {".mp3"},
    "video/mp4": {".mp4"},
}


def validate_file_type_match(
    detected_mime: str,
    claimed_extension: str,
) -> bool:
    """Check whether a detected MIME type is compatible with the claimed file extension.

    Guards against spoofed extensions (e.g. ``malware.exe`` renamed to ``report.pdf``).

    Returns True when compatible or undetermined; False only on clear mismatch.
    """
    if not detected_mime or not claimed_extension:
        return True

    claimed_extension = claimed_extension.lower()
    if not claimed_extension.startswith("."):
        claimed_extension = "." + claimed_extension

    if detected_mime == "application/octet-stream":
        return True

    compatible_exts = _MIME_TO_EXTENSIONS.get(detected_mime)
    if compatible_exts is None:
        return True

    return claimed_extension in compatible_exts


_INTERNAL_FILTER_FIELDS = frozenset({"_source_file_url"})


def _filters_from_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return a copy of metadata with internal fields stripped for use as vector_db filters."""
    if not metadata:
        return metadata
    return {k: v for k, v in metadata.items() if k not in _INTERNAL_FILTER_FIELDS}
