from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest

from agno.knowledge.storage.base import PageImageStorage
from agno.media import Audio, File, Image, Video
from agno.models.message import Message
from agno.run.agent import RunOutput
from agno.session import AgentSession
from agno.utils.media_storage import (
    async_sign_media_object,
    async_upload_media_object,
    sign_media_object,
    upload_media_in_session,
    upload_media_object,
    sign_media_in_session,
    async_upload_media_in_session,
    async_sign_media_in_session,
)


# ---------------------------------------------------------------------------
# Mock storage
# ---------------------------------------------------------------------------


@dataclass
class MockStorage(PageImageStorage):
    """In-memory mock of PageImageStorage for testing."""

    _uploaded: dict = field(default_factory=dict, repr=False)
    is_private: bool = field(default=True, repr=False)
    custom_domain: str = field(default="", repr=False)
    max_retries: int = field(default=0, repr=False)
    retry_base_delay: float = field(default=0.0, repr=False)

    BASE_URL = "https://mock-oss.example.com"

    def upload(self, local_path: str, object_key: str, content_type=None) -> str:
        return self._make_url(object_key)

    def upload_bytes(self, data: bytes, object_key: str, content_type=None) -> str:
        self._uploaded[object_key] = data
        return self._make_url(object_key)

    def sign_url(self, base_url: str, expires: int = 3600) -> str:
        return f"{base_url}?signature=mock&expires={expires}"

    def get_signed_url(self, key: str, expires: int = 3600) -> str:
        return self.sign_url(self._make_url(key), expires)

    def delete(self, object_key: str) -> bool:
        return self._uploaded.pop(object_key, None) is not None

    def exists(self, object_key: str) -> bool:
        return object_key in self._uploaded

    def extract_key_from_url(self, url: str) -> str | None:
        prefix = f"{self.BASE_URL}/"
        if url.startswith(prefix):
            return url[len(prefix) :].split("?")[0]
        return None

    def _make_url(self, object_key: str) -> str:
        return f"{self.BASE_URL}/{object_key}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(**overrides):
    """Create a mock Agent with media_storage configured."""
    agent = MagicMock()
    agent.media_storage = MockStorage()
    agent.media_storage_key_prefix = "agent_media"
    agent.media_url_signature_expires = 7200
    for k, v in overrides.items():
        setattr(agent, k, v)
    return agent


# ---------------------------------------------------------------------------
# Tests: upload_media_object
# ---------------------------------------------------------------------------


class TestUploadMediaObject:
    def test_upload_image_with_bytes(self):
        storage = MockStorage()
        img = Image(content=b"fake-png-data", mime_type="image/png")

        result = upload_media_object(img, storage, "agent_media", "sess-1")

        assert result is True
        assert img.url is not None
        assert "mock-oss.example.com" in img.url
        assert img.content is None

    def test_skip_image_with_url(self):
        storage = MockStorage()
        img = Image(url="https://example.com/image.png")

        result = upload_media_object(img, storage, "agent_media", "sess-1")

        assert result is False
        assert storage._uploaded == {}

    def test_all_media_types(self):
        storage = MockStorage()
        media_objects = [
            Image(content=b"img-data", mime_type="image/png"),
            Audio(content=b"aud-data", mime_type="audio/mp3"),
            Video(content=b"vid-data", mime_type="video/mp4"),
            File(content=b"file-data", mime_type="application/pdf"),
        ]

        for media in media_objects:
            result = upload_media_object(media, storage, "agent_media", "sess-1")
            assert result is True
            assert media.url is not None
            assert media.content is None

    def test_file_with_string_content(self):
        storage = MockStorage()
        f = File(content="csv,data\n1,2", mime_type="text/csv")

        result = upload_media_object(f, storage, "agent_media", "sess-1")

        assert result is True
        assert f.url is not None
        assert f.content is None

    def test_upload_failure_raises(self):
        storage = MockStorage()
        img = Image(content=b"data", mime_type="image/png")

        with patch.object(storage, "upload_bytes", side_effect=Exception("OSS down")):
            with pytest.raises(Exception, match="OSS down"):
                upload_media_object(img, storage, "agent_media", "sess-1")

    def test_object_key_format(self):
        storage = MockStorage()
        img = Image(content=b"data", mime_type="image/png", id="test-id-123")

        upload_media_object(img, storage, "prefix", "sess-abc")

        assert "prefix/sess-abc/test-id-123" in img.url


# ---------------------------------------------------------------------------
# Tests: async_upload_media_object
# ---------------------------------------------------------------------------


class TestAsyncUploadMediaObject:
    @pytest.mark.asyncio
    async def test_async_upload_image(self):
        storage = MockStorage()
        img = Image(content=b"async-data", mime_type="image/png")

        result = await async_upload_media_object(img, storage, "agent_media", "sess-1")

        assert result is True
        assert img.url is not None
        assert img.content is None

    @pytest.mark.asyncio
    async def test_async_skip_url_image(self):
        storage = MockStorage()
        img = Image(url="https://example.com/img.png")

        result = await async_upload_media_object(img, storage, "agent_media", "sess-1")

        assert result is False


# ---------------------------------------------------------------------------
# Tests: sign_media_object
# ---------------------------------------------------------------------------


class TestSignMediaObject:
    def test_sign_oss_url(self):
        storage = MockStorage()
        img = Image(url="https://mock-oss.example.com/agent_media/sess/img.png")

        sign_media_object(img, storage, expires=3600)

        assert "signature=mock" in img.url
        assert "expires=3600" in img.url

    def test_skip_external_url(self):
        storage = MockStorage()
        original_url = "https://example.com/image.png"
        img = Image(url=original_url)

        sign_media_object(img, storage, expires=3600)

        assert img.url == original_url

    def test_skip_no_url(self):
        """Media with content but no URL should be skipped."""
        storage = MockStorage()
        img = Image(content=b"data", mime_type="image/png")

        sign_media_object(img, storage, expires=3600)
        # url should still be None
        assert img.url is None


class TestAsyncSignMediaObject:
    @pytest.mark.asyncio
    async def test_async_sign_oss_url(self):
        storage = MockStorage()
        img = Image(url="https://mock-oss.example.com/agent_media/sess/img.png")

        await async_sign_media_object(img, storage, expires=3600)

        assert "signature=mock" in img.url

    @pytest.mark.asyncio
    async def test_async_skip_external_url(self):
        storage = MockStorage()
        url = "https://example.com/img.png"
        img = Image(url=url)

        await async_sign_media_object(img, storage, expires=3600)

        assert img.url == url


# ---------------------------------------------------------------------------
# Tests: session-level operations
# ---------------------------------------------------------------------------


class TestUploadMediaInSession:
    def _make_session_with_media(self):
        """Create an AgentSession with media in various locations."""
        img1 = Image(content=b"img-bytes-1", mime_type="image/png", id="img-1")
        img2 = Image(content=b"img-bytes-2", mime_type="image/jpeg", id="img-2")
        aud = Audio(content=b"aud-bytes", mime_type="audio/mp3", id="aud-1")
        resp_aud = Audio(content=b"resp-aud-bytes", mime_type="audio/wav", id="resp-aud-1")
        vid = Video(content=b"vid-bytes", mime_type="video/mp4", id="vid-1")
        f = File(content=b"file-bytes", mime_type="application/pdf", id="file-1")

        msg = Message(
            role="user",
            content="Hello",
            images=[img1],
            audio=[aud],
            files=[f],
        )

        run = RunOutput(
            images=[img2],
            videos=[vid],
            response_audio=resp_aud,
            messages=[msg],
        )

        session = AgentSession(
            session_id="test-session",
            session_data={"session_state": {}},
            runs=[run],
        )
        return session

    def test_upload_all_media_in_session(self):
        agent = _make_agent()
        session = self._make_session_with_media()
        storage = agent.media_storage

        upload_media_in_session(agent, session)

        # All bytes should be uploaded
        assert len(storage._uploaded) >= 5
        # All media should have URLs now
        run = session.runs[0]
        assert run.images[0].url is not None
        assert run.images[0].content is None
        assert run.videos[0].url is not None
        assert run.videos[0].content is None
        assert run.response_audio.url is not None
        assert run.response_audio.content is None
        msg = run.messages[0]
        assert msg.images[0].url is not None
        assert msg.images[0].content is None
        assert msg.audio[0].url is not None
        assert msg.audio[0].content is None
        assert msg.files[0].url is not None
        assert msg.files[0].content is None

    def test_to_dict_no_base64_after_upload(self):
        agent = _make_agent()
        session = self._make_session_with_media()

        upload_media_in_session(agent, session)

        session_dict = session.to_dict()
        runs = session_dict.get("runs", [])
        assert len(runs) == 1

        # Check no base64 content in run images
        for img_dict in runs[0].get("images", []):
            assert "content" not in img_dict
            assert "url" in img_dict

        # Check no base64 content in messages
        for msg_dict in runs[0].get("messages", []):
            for img_dict in msg_dict.get("images", []):
                assert "content" not in img_dict
                assert "url" in img_dict

    def test_no_media_storage_is_noop(self):
        agent = _make_agent(media_storage=None)
        session = self._make_session_with_media()

        # Should not raise
        upload_media_in_session(agent, session)

        # Media should be unchanged
        assert session.runs[0].images[0].content is not None

    def test_no_runs_is_noop(self):
        agent = _make_agent()
        session = AgentSession(session_id="empty", session_data={"session_state": {}})

        upload_media_in_session(agent, session)
        # Should not raise

    def test_external_urls_unchanged(self):
        agent = _make_agent()
        external_url = "https://example.com/image.png"
        img = Image(url=external_url)
        run = RunOutput(images=[img])
        session = AgentSession(session_id="ext-test", session_data={"session_state": {}}, runs=[run])

        upload_media_in_session(agent, session)

        assert img.url == external_url


class TestSignMediaInSession:
    def test_sign_all_oss_urls(self):
        storage = MockStorage()
        agent = _make_agent()
        agent.media_storage = storage

        img = Image(url="https://mock-oss.example.com/agent_media/sess/img.png")
        aud = Audio(url="https://mock-oss.example.com/agent_media/sess/aud.mp3")
        msg = Message(role="user", content="Hi", images=[img], audio=[aud])
        run = RunOutput(messages=[msg])
        session = AgentSession(session_id="sign-test", session_data={"session_state": {}}, runs=[run])

        sign_media_in_session(agent, session)

        assert "signature=mock" in img.url
        assert "signature=mock" in aud.url

    def test_external_urls_not_signed(self):
        agent = _make_agent()
        ext_img = Image(url="https://example.com/image.png")
        run = RunOutput(images=[ext_img])
        session = AgentSession(session_id="ext-sign", session_data={"session_state": {}}, runs=[run])

        sign_media_in_session(agent, session)

        assert ext_img.url == "https://example.com/image.png"

    def test_no_media_storage_is_noop(self):
        agent = _make_agent(media_storage=None)
        img = Image(url="https://mock-oss.example.com/x.png")
        run = RunOutput(images=[img])
        session = AgentSession(session_id="noop", session_data={"session_state": {}}, runs=[run])

        sign_media_in_session(agent, session)
        assert "signature" not in img.url


class TestAsyncSessionOperations:
    @pytest.mark.asyncio
    async def test_async_upload_session(self):
        agent = _make_agent()
        img = Image(content=b"async-img", mime_type="image/png", id="async-img-1")
        run = RunOutput(images=[img])
        session = AgentSession(session_id="async-test", session_data={"session_state": {}}, runs=[run])

        await async_upload_media_in_session(agent, session)

        assert img.url is not None
        assert img.content is None

    @pytest.mark.asyncio
    async def test_async_sign_session(self):
        agent = _make_agent()
        img = Image(url="https://mock-oss.example.com/agent_media/s/img.png")
        run = RunOutput(images=[img])
        session = AgentSession(session_id="async-sign", session_data={"session_state": {}}, runs=[run])

        await async_sign_media_in_session(agent, session)

        assert "signature=mock" in img.url


# ---------------------------------------------------------------------------
# Tests: end-to-end data flow
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_upload_then_serialize_then_deserialize_then_sign(self):
        """Simulate full lifecycle: upload → serialize → deserialize → sign."""
        agent = _make_agent()

        # 1. Create media with bytes
        img = Image(content=b"e2e-image-data", mime_type="image/png", id="e2e-img")
        msg = Message(role="assistant", content="Here is an image", images=[img])
        # agent_id is required for AgentSession.from_dict to recognize the run
        run = RunOutput(agent_id="test-agent", content="done", messages=[msg])
        session = AgentSession(
            session_id="e2e-session",
            session_data={"session_state": {}},
            runs=[run],
        )

        # 2. Upload (simulating save_session)
        upload_media_in_session(agent, session)

        # 3. Serialize (simulating DB write)
        session_dict = session.to_dict()
        runs = session_dict["runs"]
        assert "content" not in runs[0]["messages"][0]["images"][0]
        assert "url" in runs[0]["messages"][0]["images"][0]

        # 4. Deserialize (simulating DB read)
        loaded_session = AgentSession.from_dict(session_dict)
        assert loaded_session is not None
        loaded_run = loaded_session.runs[0]
        loaded_msg = loaded_run.messages[0]
        loaded_img = loaded_msg.images[0]

        # Image should have url (unsigned), no content
        assert loaded_img.url is not None
        assert "mock-oss.example.com" in loaded_img.url
        assert "signature" not in loaded_img.url  # Not signed yet

        # 5. Sign (simulating get_session)
        sign_media_in_session(agent, loaded_session)

        assert "signature=mock" in loaded_img.url
        assert "expires=7200" in loaded_img.url

    def test_backward_compatible_with_base64_data(self):
        """Old base64 data should still work through the existing reconstruct path."""
        import base64

        original = b"legacy-image-data"
        b64 = base64.b64encode(original).decode("utf-8")

        img_data = {"id": "legacy-img", "content": b64, "mime_type": "image/png"}
        from agno.utils.media import reconstruct_image_from_dict

        img = reconstruct_image_from_dict(img_data)

        assert isinstance(img, Image)
        assert img.content == original

    def test_mixed_oss_and_external_urls_in_same_session(self):
        """Session with both OSS-uploaded and external URLs."""
        agent = _make_agent()

        oss_img = Image(content=b"oss-data", mime_type="image/png", id="oss-1")
        ext_img = Image(url="https://cdn.example.com/external.png")

        run = RunOutput(images=[oss_img, ext_img])
        session = AgentSession(
            session_id="mixed",
            session_data={"session_state": {}},
            runs=[run],
        )

        upload_media_in_session(agent, session)

        assert oss_img.url is not None
        assert oss_img.content is None
        assert ext_img.url == "https://cdn.example.com/external.png"

        sign_media_in_session(agent, session)

        assert "signature=mock" in oss_img.url
        assert ext_img.url == "https://cdn.example.com/external.png"
