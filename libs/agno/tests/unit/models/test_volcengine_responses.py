"""Tests for VolcengineResponses redundant data stripping."""

from agno.models.response import ModelResponse
from agno.models.volcengine.responses import VolcengineResponses


def _make_model(reasoning_content=None, provider_data=None):
    model_response = ModelResponse()
    model_response.reasoning_content = reasoning_content
    model_response.provider_data = provider_data
    return model_response


def test_strip_encrypted_content():
    """encrypted_content (large base64 blob) should be removed."""
    model = VolcengineResponses(id="test")
    mr = _make_model(
        provider_data={
            "response_id": "resp_123",
            "reasoning_output": {
                "type": "reasoning",
                "id": "rs_123",
                "summary": [{"text": "some reasoning", "type": "summary_text"}],
                "encrypted_content": "djEvWRNpOZEHoYx8..." * 50,
                "status": "completed",
            },
        }
    )
    model._strip_redundant_provider_data(mr)

    ro = mr.provider_data["reasoning_output"]
    assert "encrypted_content" not in ro
    assert ro["type"] == "reasoning"
    assert mr.provider_data["response_id"] == "resp_123"


def test_strip_duplicate_summary():
    """summary text that duplicates reasoning_content should be removed."""
    model = VolcengineResponses(id="test")
    mr = _make_model(
        reasoning_content="I should greet the user warmly.",
        provider_data={
            "response_id": "resp_456",
            "reasoning_output": {
                "type": "reasoning",
                "summary": [{"text": "I should greet the user warmly.", "type": "summary_text"}],
                "encrypted_content": "base64blob",
            },
        },
    )
    model._strip_redundant_provider_data(mr)

    ro = mr.provider_data.get("reasoning_output", {})
    assert "encrypted_content" not in ro
    assert "summary" not in ro


def test_no_reasoning_output_noop():
    """If no reasoning_output, nothing should be touched."""
    model = VolcengineResponses(id="test")
    mr = _make_model(
        provider_data={"response_id": "resp_789"},
    )
    model._strip_redundant_provider_data(mr)

    assert mr.provider_data == {"response_id": "resp_789"}


def test_none_provider_data_noop():
    """None provider_data should not crash."""
    model = VolcengineResponses(id="test")
    mr = _make_model(provider_data=None)
    model._strip_redundant_provider_data(mr)

    assert mr.provider_data is None


def test_empty_reasoning_output_removed():
    """If reasoning_output only has 'type' left, remove it entirely."""
    model = VolcengineResponses(id="test")
    mr = _make_model(
        reasoning_content="some reasoning",
        provider_data={
            "response_id": "resp_abc",
            "reasoning_output": {
                "type": "reasoning",
                "encrypted_content": "blob",
                "summary": [{"text": "some reasoning", "type": "summary_text"}],
            },
        },
    )
    model._strip_redundant_provider_data(mr)

    assert "reasoning_output" not in mr.provider_data
    assert mr.provider_data["response_id"] == "resp_abc"


def test_summary_kept_when_no_reasoning_content():
    """If no reasoning_content, summary should NOT be stripped (it's the only copy)."""
    model = VolcengineResponses(id="test")
    mr = _make_model(
        reasoning_content=None,
        provider_data={
            "response_id": "resp_def",
            "reasoning_output": {
                "type": "reasoning",
                "summary": [{"text": "unique reasoning", "type": "summary_text"}],
                "encrypted_content": "blob",
            },
        },
    )
    model._strip_redundant_provider_data(mr)

    ro = mr.provider_data.get("reasoning_output", {})
    assert "summary" in ro
    assert "encrypted_content" not in ro
