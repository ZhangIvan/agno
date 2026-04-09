"""Upload agent media to OSS and sign URLs on retrieval.

When an Agent is configured with ``media_storage`` (a :class:`PageImageStorage`
instance), every media object (Image, Audio, Video, File) that carries raw
bytes will be uploaded to OSS *before* the session is persisted to the
database.  The in-memory object is then rewritten in-place: ``content`` is
cleared and ``url`` is set to the permanent (unsigned) OSS URL.

On load, OSS URLs are re-signed with short-lived credentials so the caller
receives working links.  External URLs pass through unchanged.
"""

from __future__ import annotations

import mimetypes
from typing import TYPE_CHECKING, Optional, Sequence, Union
from uuid import uuid4

if TYPE_CHECKING:
    from agno.agent.agent import Agent
    from agno.knowledge.storage.base import PageImageStorage
    from agno.session import AgentSession, TeamSession, WorkflowSession

from agno.media import Audio, File, Image, Video
from agno.models.message import Message
from agno.run.agent import RunInput, RunOutput
from agno.utils.log import log_debug

# ---------------------------------------------------------------------------
# Type alias for any media object
# ---------------------------------------------------------------------------
_Media = Union[Image, Audio, Video, File]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _guess_extension(media: _Media) -> str:
    """Return a file extension (with leading dot) for *media*."""
    # 1. Explicit format field (e.g. "png", "mp4")
    if getattr(media, "format", None):
        fmt = media.format  # type: ignore[union-attr]
        return f".{fmt}" if not fmt.startswith(".") else fmt

    # 2. Infer from mime_type
    mime_type = getattr(media, "mime_type", None)
    if mime_type:
        ext = mimetypes.guess_extension(mime_type)
        if ext:
            return ext

    # 3. Fallback
    return ".bin"


# ---------------------------------------------------------------------------
# Single media object operations
# ---------------------------------------------------------------------------


def upload_media_object(
    media: _Media,
    storage: "PageImageStorage",
    key_prefix: str,
    session_id: str,
) -> bool:
    """Upload a single media object's bytes to OSS.

    On success the media object is modified in-place:
    * ``media.url`` is set to the unsigned OSS URL.
    * ``media.content`` is cleared (set to ``None``).

    Returns ``True`` if an upload was performed, ``False`` if the object
    was skipped (already has a URL, or no bytes to upload).

    Raises on upload failure (the caller decides how to handle it).
    """
    if media.url is not None:
        return False

    content_bytes = media.get_content_bytes()
    if content_bytes is None:
        return False

    media_id = media.id or str(uuid4())
    ext = _guess_extension(media)
    object_key = f"{key_prefix}/{session_id}/{media_id}{ext}"

    content_type = getattr(media, "mime_type", None) or storage.guess_content_type(object_key)

    url = storage.upload_bytes(content_bytes, object_key, content_type)

    media.url = url  # type: ignore[assignment]
    media.content = None  # type: ignore[assignment]
    log_debug(f"Uploaded media {media_id} to OSS: {object_key}")
    return True


async def async_upload_media_object(
    media: _Media,
    storage: "PageImageStorage",
    key_prefix: str,
    session_id: str,
) -> bool:
    """Async variant of :func:`upload_media_object`."""
    if media.url is not None:
        return False

    content_bytes = media.get_content_bytes()
    if content_bytes is None:
        return False

    media_id = media.id or str(uuid4())
    ext = _guess_extension(media)
    object_key = f"{key_prefix}/{session_id}/{media_id}{ext}"

    content_type = getattr(media, "mime_type", None) or storage.guess_content_type(object_key)

    url = await storage.async_upload_bytes(content_bytes, object_key, content_type)

    media.url = url  # type: ignore[assignment]
    media.content = None  # type: ignore[assignment]
    log_debug(f"Uploaded media {media_id} to OSS (async): {object_key}")
    return True


def sign_media_object(
    media: _Media,
    storage: "PageImageStorage",
    expires: int,
) -> None:
    """Sign an OSS URL on a media object in-place.

    External URLs (not belonging to this storage backend) are left unchanged.
    """
    if media.url is None:
        return

    key = storage.extract_key_from_url(media.url)
    if key is None:
        return  # External URL

    media.url = storage.sign_url(media.url, expires=expires)  # type: ignore[assignment]


async def async_sign_media_object(
    media: _Media,
    storage: "PageImageStorage",
    expires: int,
) -> None:
    """Async variant of :func:`sign_media_object`."""
    if media.url is None:
        return

    key = storage.extract_key_from_url(media.url)
    if key is None:
        return

    media.url = await storage.async_sign_url(media.url, expires=expires)  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Media list helpers
# ---------------------------------------------------------------------------


def _process_media_list(
    media_list: Optional[Sequence[_Media]],
    storage: "PageImageStorage",
    key_prefix: str,
    session_id: str,
    upload: bool = True,
    expires: int = 7200,
) -> None:
    """Process a list of media objects (upload or sign)."""
    if not media_list:
        return
    for media in media_list:
        if upload:
            upload_media_object(media, storage, key_prefix, session_id)
        else:
            sign_media_object(media, storage, expires)


async def _async_process_media_list(
    media_list: Optional[Sequence[_Media]],
    storage: "PageImageStorage",
    key_prefix: str,
    session_id: str,
    upload: bool = True,
    expires: int = 7200,
) -> None:
    """Async variant of :func:`_process_media_list`.

    Uses ``asyncio.gather`` for concurrent uploads/signing.
    """
    import asyncio

    if not media_list:
        return
    if upload:
        await asyncio.gather(
            *[async_upload_media_object(m, storage, key_prefix, session_id) for m in media_list]
        )
    else:
        await asyncio.gather(*[async_sign_media_object(m, storage, expires) for m in media_list])


# ---------------------------------------------------------------------------
# Message-level traversal
# ---------------------------------------------------------------------------


def _process_message_media(
    msg: Message,
    storage: "PageImageStorage",
    key_prefix: str,
    session_id: str,
    upload: bool = True,
    expires: int = 7200,
) -> None:
    """Process all media on a single Message."""
    _process_media_list(msg.images, storage, key_prefix, session_id, upload, expires)
    _process_media_list(msg.audio, storage, key_prefix, session_id, upload, expires)
    _process_media_list(msg.videos, storage, key_prefix, session_id, upload, expires)
    _process_media_list(msg.files, storage, key_prefix, session_id, upload, expires)

    # Output media (single objects)
    if msg.audio_output:
        if upload:
            upload_media_object(msg.audio_output, storage, key_prefix, session_id)
        else:
            sign_media_object(msg.audio_output, storage, expires)
    if msg.image_output:
        if upload:
            upload_media_object(msg.image_output, storage, key_prefix, session_id)
        else:
            sign_media_object(msg.image_output, storage, expires)
    if msg.video_output:
        if upload:
            upload_media_object(msg.video_output, storage, key_prefix, session_id)
        else:
            sign_media_object(msg.video_output, storage, expires)
    if msg.file_output:
        if upload:
            upload_media_object(msg.file_output, storage, key_prefix, session_id)
        else:
            sign_media_object(msg.file_output, storage, expires)


async def _async_process_message_media(
    msg: Message,
    storage: "PageImageStorage",
    key_prefix: str,
    session_id: str,
    upload: bool = True,
    expires: int = 7200,
) -> None:
    """Async variant of :func:`_process_message_media`."""
    await _async_process_media_list(msg.images, storage, key_prefix, session_id, upload, expires)
    await _async_process_media_list(msg.audio, storage, key_prefix, session_id, upload, expires)
    await _async_process_media_list(msg.videos, storage, key_prefix, session_id, upload, expires)
    await _async_process_media_list(msg.files, storage, key_prefix, session_id, upload, expires)

    if msg.audio_output:
        if upload:
            await async_upload_media_object(msg.audio_output, storage, key_prefix, session_id)
        else:
            await async_sign_media_object(msg.audio_output, storage, expires)
    if msg.image_output:
        if upload:
            await async_upload_media_object(msg.image_output, storage, key_prefix, session_id)
        else:
            await async_sign_media_object(msg.image_output, storage, expires)
    if msg.video_output:
        if upload:
            await async_upload_media_object(msg.video_output, storage, key_prefix, session_id)
        else:
            await async_sign_media_object(msg.video_output, storage, expires)
    if msg.file_output:
        if upload:
            await async_upload_media_object(msg.file_output, storage, key_prefix, session_id)
        else:
            await async_sign_media_object(msg.file_output, storage, expires)


# ---------------------------------------------------------------------------
# RunInput-level traversal
# ---------------------------------------------------------------------------


def _process_run_input_media(
    run_input: Optional[RunInput],
    storage: "PageImageStorage",
    key_prefix: str,
    session_id: str,
    upload: bool = True,
    expires: int = 7200,
) -> None:
    if run_input is None:
        return
    _process_media_list(run_input.images, storage, key_prefix, session_id, upload, expires)
    _process_media_list(run_input.videos, storage, key_prefix, session_id, upload, expires)
    _process_media_list(run_input.audios, storage, key_prefix, session_id, upload, expires)
    _process_media_list(run_input.files, storage, key_prefix, session_id, upload, expires)


async def _async_process_run_input_media(
    run_input: Optional[RunInput],
    storage: "PageImageStorage",
    key_prefix: str,
    session_id: str,
    upload: bool = True,
    expires: int = 7200,
) -> None:
    if run_input is None:
        return
    await _async_process_media_list(run_input.images, storage, key_prefix, session_id, upload, expires)
    await _async_process_media_list(run_input.videos, storage, key_prefix, session_id, upload, expires)
    await _async_process_media_list(run_input.audios, storage, key_prefix, session_id, upload, expires)
    await _async_process_media_list(run_input.files, storage, key_prefix, session_id, upload, expires)


# ---------------------------------------------------------------------------
# RunOutput-level traversal
# ---------------------------------------------------------------------------


def _process_run_output(
    run: RunOutput,
    storage: "PageImageStorage",
    key_prefix: str,
    session_id: str,
    upload: bool = True,
    expires: int = 7200,
) -> None:
    """Process all media in a single RunOutput."""
    # Direct media lists
    _process_media_list(run.images, storage, key_prefix, session_id, upload, expires)
    _process_media_list(run.videos, storage, key_prefix, session_id, upload, expires)
    _process_media_list(run.audio, storage, key_prefix, session_id, upload, expires)
    _process_media_list(run.files, storage, key_prefix, session_id, upload, expires)

    # Single output media
    if run.response_audio:
        if upload:
            upload_media_object(run.response_audio, storage, key_prefix, session_id)
        else:
            sign_media_object(run.response_audio, storage, expires)

    # Input media
    _process_run_input_media(run.input, storage, key_prefix, session_id, upload, expires)

    # Messages
    if run.messages:
        for msg in run.messages:
            _process_message_media(msg, storage, key_prefix, session_id, upload, expires)

    # Additional input messages
    if run.additional_input:
        for msg in run.additional_input:
            _process_message_media(msg, storage, key_prefix, session_id, upload, expires)

    # Reasoning messages
    if run.reasoning_messages:
        for msg in run.reasoning_messages:
            _process_message_media(msg, storage, key_prefix, session_id, upload, expires)

    # Events
    if run.events:
        for event in run.events:
            _process_event_media(event, storage, key_prefix, session_id, upload, expires)


async def _async_process_run_output(
    run: RunOutput,
    storage: "PageImageStorage",
    key_prefix: str,
    session_id: str,
    upload: bool = True,
    expires: int = 7200,
) -> None:
    """Async variant of :func:`_process_run_output`."""
    await _async_process_media_list(run.images, storage, key_prefix, session_id, upload, expires)
    await _async_process_media_list(run.videos, storage, key_prefix, session_id, upload, expires)
    await _async_process_media_list(run.audio, storage, key_prefix, session_id, upload, expires)
    await _async_process_media_list(run.files, storage, key_prefix, session_id, upload, expires)

    if run.response_audio:
        if upload:
            await async_upload_media_object(run.response_audio, storage, key_prefix, session_id)
        else:
            await async_sign_media_object(run.response_audio, storage, expires)

    await _async_process_run_input_media(run.input, storage, key_prefix, session_id, upload, expires)

    if run.messages:
        for msg in run.messages:
            await _async_process_message_media(msg, storage, key_prefix, session_id, upload, expires)

    if run.additional_input:
        for msg in run.additional_input:
            await _async_process_message_media(msg, storage, key_prefix, session_id, upload, expires)

    if run.reasoning_messages:
        for msg in run.reasoning_messages:
            await _async_process_message_media(msg, storage, key_prefix, session_id, upload, expires)

    if run.events:
        for event in run.events:
            await _async_process_event_media(event, storage, key_prefix, session_id, upload, expires)


# ---------------------------------------------------------------------------
# Event-level traversal
# ---------------------------------------------------------------------------


def _process_event_media(
    event: object,
    storage: "PageImageStorage",
    key_prefix: str,
    session_id: str,
    upload: bool = True,
    expires: int = 7200,
) -> None:
    """Process media on a run event (duck-typed)."""
    # RunContentEvent has single 'image' and 'response_audio'
    image = getattr(event, "image", None)
    if image:
        if upload:
            upload_media_object(image, storage, key_prefix, session_id)
        else:
            sign_media_object(image, storage, expires)

    response_audio = getattr(event, "response_audio", None)
    if response_audio:
        if upload:
            upload_media_object(response_audio, storage, key_prefix, session_id)
        else:
            sign_media_object(response_audio, storage, expires)

    # RunCompletedEvent has lists
    for attr in ("images", "videos", "audio", "files"):
        _process_media_list(getattr(event, attr, None), storage, key_prefix, session_id, upload, expires)

    # Events may have messages too
    for attr in ("messages", "additional_input", "reasoning_messages"):
        msgs = getattr(event, attr, None)
        if msgs:
            for msg in msgs:
                _process_message_media(msg, storage, key_prefix, session_id, upload, expires)


async def _async_process_event_media(
    event: object,
    storage: "PageImageStorage",
    key_prefix: str,
    session_id: str,
    upload: bool = True,
    expires: int = 7200,
) -> None:
    """Async variant of :func:`_process_event_media`."""
    image = getattr(event, "image", None)
    if image:
        if upload:
            await async_upload_media_object(image, storage, key_prefix, session_id)
        else:
            await async_sign_media_object(image, storage, expires)

    response_audio = getattr(event, "response_audio", None)
    if response_audio:
        if upload:
            await async_upload_media_object(response_audio, storage, key_prefix, session_id)
        else:
            await async_sign_media_object(response_audio, storage, expires)

    for attr in ("images", "videos", "audio", "files"):
        await _async_process_media_list(getattr(event, attr, None), storage, key_prefix, session_id, upload, expires)

    for attr in ("messages", "additional_input", "reasoning_messages"):
        msgs = getattr(event, attr, None)
        if msgs:
            for msg in msgs:
                await _async_process_message_media(msg, storage, key_prefix, session_id, upload, expires)


# ---------------------------------------------------------------------------
# Public API: session-level operations
# ---------------------------------------------------------------------------


def upload_media_in_session(
    agent: "Agent",
    session: "Union[AgentSession, TeamSession, WorkflowSession]",
) -> None:
    """Upload all media bytes in *session* to OSS.

    Walks every run and message, uploading any media that has ``content``
    bytes and no URL.  On success the in-memory objects are rewritten with
    an unsigned OSS URL and cleared content.

    Raises on upload failure (no fallback to base64).
    """
    storage = agent.media_storage
    if storage is None:
        return

    key_prefix = agent.media_storage_key_prefix
    session_id = session.session_id

    runs = getattr(session, "runs", None)
    if not runs:
        return

    for run in runs:
        if hasattr(run, "images"):
            _process_run_output(run, storage, key_prefix, session_id, upload=True)


async def async_upload_media_in_session(
    agent: "Agent",
    session: "Union[AgentSession, TeamSession, WorkflowSession]",
) -> None:
    """Async variant of :func:`upload_media_in_session`."""
    storage = agent.media_storage
    if storage is None:
        return

    key_prefix = agent.media_storage_key_prefix
    session_id = session.session_id

    runs = getattr(session, "runs", None)
    if not runs:
        return

    for run in runs:
        if hasattr(run, "images"):
            await _async_process_run_output(run, storage, key_prefix, session_id, upload=True)


def sign_media_in_session(
    agent: "Agent",
    session: "Union[AgentSession, TeamSession, WorkflowSession]",
) -> None:
    """Sign all OSS URLs in *session*.

    Walks every run and message, signing any URL that belongs to the
    configured storage backend.  External URLs are left unchanged.
    """
    storage = agent.media_storage
    if storage is None:
        return

    key_prefix = agent.media_storage_key_prefix
    session_id = session.session_id
    expires = agent.media_url_signature_expires

    runs = getattr(session, "runs", None)
    if not runs:
        return

    for run in runs:
        if hasattr(run, "images"):
            _process_run_output(run, storage, key_prefix, session_id, upload=False, expires=expires)


async def async_sign_media_in_session(
    agent: "Agent",
    session: "Union[AgentSession, TeamSession, WorkflowSession]",
) -> None:
    """Async variant of :func:`sign_media_in_session`."""
    storage = agent.media_storage
    if storage is None:
        return

    key_prefix = agent.media_storage_key_prefix
    session_id = session.session_id
    expires = agent.media_url_signature_expires

    runs = getattr(session, "runs", None)
    if not runs:
        return

    for run in runs:
        if hasattr(run, "images"):
            await _async_process_run_output(run, storage, key_prefix, session_id, upload=False, expires=expires)
