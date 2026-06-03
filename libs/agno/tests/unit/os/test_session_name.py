"""Tests for session name extraction in os/utils.py."""

import json

from agno.os.utils import (
    get_session_name,
    extract_input_media,
    _extract_session_name_from_content,
    _session_name_from_input,
    _normalize_run,
    _REFERENCE_MARKERS,
    _SESSION_NAME_MAX_LENGTH,
)


# ============================================================
# _extract_session_name_from_content
# ============================================================


def test_extract_clean_content():
    assert _extract_session_name_from_content("Hello world") == "Hello world"


def test_extract_empty():
    assert _extract_session_name_from_content("") == ""
    assert _extract_session_name_from_content(None) == ""


def test_extract_strips_references():
    content = "看看斯贝利单抗的机制是什么\n\nUse the following references from the knowledge base if it helps:\n<references>\n[{\"content\": \"...huge doc...\"}]"
    result = _extract_session_name_from_content(content)
    assert result == "看看斯贝利单抗的机制是什么"
    assert "references" not in result
    assert "knowledge" not in result


def test_extract_strips_references_tag():
    content = "My query\n\n<references>\nsome docs"
    result = _extract_session_name_from_content(content)
    assert result == "My query"


def test_extract_strips_additional_context():
    content = "My query\n\n<additional context>\nsome deps"
    result = _extract_session_name_from_content(content)
    assert result == "My query"


def test_extract_truncates_long_content():
    long_content = "x" * 200
    result = _extract_session_name_from_content(long_content)
    assert len(result) == _SESSION_NAME_MAX_LENGTH
    assert result.endswith("...")


def test_extract_truncates_exact_boundary():
    content = "x" * _SESSION_NAME_MAX_LENGTH
    result = _extract_session_name_from_content(content)
    assert len(result) == _SESSION_NAME_MAX_LENGTH
    assert not result.endswith("...")


def test_extract_truncates_one_over_boundary():
    content = "x" * (_SESSION_NAME_MAX_LENGTH + 1)
    result = _extract_session_name_from_content(content)
    assert len(result) == _SESSION_NAME_MAX_LENGTH
    assert result.endswith("...")


def test_extract_marker_at_start():
    """If content starts with marker (idx==0), should not strip."""
    content = "\n\n<references>\ndocs"
    result = _extract_session_name_from_content(content)
    # idx==0, so marker not stripped; content is returned as-is (truncated)
    assert len(result) <= _SESSION_NAME_MAX_LENGTH


def test_extract_chinese_content():
    chinese = "斯贝利单抗的机制是什么"
    result = _extract_session_name_from_content(chinese)
    assert result == chinese


def test_extract_real_world_knowledge_query():
    content = (
        "看看斯贝利单抗的机制是什么\n\n"
        "Use the following references from the knowledge base if it helps:\n"
        "<references>\n"
        '[{"content": "y significant safety signals... (50KB of content)", "name": "doc.pdf"}]\n'
        "</references>"
    )
    result = _extract_session_name_from_content(content)
    assert result == "看看斯贝利单抗的机制是什么"


# ============================================================
# _session_name_from_input
# ============================================================


def test_input_string():
    assert _session_name_from_input("Hello world") == "Hello world"


def test_input_dict_with_content():
    run_input = {"role": "user", "content": "My query about drugs"}
    assert _session_name_from_input(run_input) == "My query about drugs"


def test_input_dict_without_content():
    run_input = {"input_content": "some value"}
    result = _session_name_from_input(run_input)
    # Falls through to stringify + extract
    assert isinstance(result, str)


def test_input_list_with_user_message():
    run_input = [
        {"role": "system", "content": "You are a helper"},
        {"role": "user", "content": "My query"},
    ]
    assert _session_name_from_input(run_input) == "My query"


def test_input_list_without_user_message():
    run_input = [
        {"role": "system", "content": "You are a helper"},
    ]
    result = _session_name_from_input(run_input)
    assert isinstance(result, str)


def test_input_unsupported_type():
    assert _session_name_from_input(42) == ""
    assert _session_name_from_input(None) == ""


def test_input_dict_with_references_in_content():
    """Content with references should be cleaned."""
    run_input = {
        "role": "user",
        "content": "My query\n\nUse the following references from the knowledge base if it helps:\n<references>\nbig docs",
    }
    result = _session_name_from_input(run_input)
    assert result == "My query"


# ============================================================
# _normalize_run
# ============================================================


def test_normalize_run_dict():
    d = {"key": "value"}
    assert _normalize_run(d) is d


def test_normalize_run_none():
    assert _normalize_run(None) == {}


def test_normalize_run_object():
    """Objects with to_dict() should be normalized."""

    class FakeRun:
        def to_dict(self):
            return {"agent_id": "agent_123"}

    result = _normalize_run(FakeRun())
    assert result == {"agent_id": "agent_123"}


# ============================================================
# get_session_name — integration tests
# ============================================================


def _make_session(session_type="agent", session_data=None, runs=None):
    return {
        "session_type": session_type,
        "session_data": session_data or {},
        "runs": runs or [],
    }


def test_session_name_from_session_data():
    """If session_data has session_name, use it directly."""
    session = _make_session(session_data={"session_name": "My Custom Session"})
    assert get_session_name(session) == "My Custom Session"


def test_session_name_from_user_message():
    session = _make_session(runs=[
        {
            "messages": [
                {"role": "system", "content": "You are a helper"},
                {"role": "user", "content": "Ask about IgA nephropathy"},
            ]
        }
    ])
    assert get_session_name(session) == "Ask about IgA nephropathy"


def test_session_name_strips_references_from_message():
    session = _make_session(runs=[
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "查看药物机制\n\n"
                        "Use the following references from the knowledge base if it helps:\n"
                        "<references>\n[{\"content\": \"50KB of docs\"}]\n"
                        "</references>"
                    ),
                },
            ]
        }
    ])
    result = get_session_name(session)
    assert result == "查看药物机制"
    assert "references" not in result


def test_session_name_no_messages_no_input():
    session = _make_session(runs=[{"messages": []}])
    assert get_session_name(session) == ""


def test_session_name_no_runs():
    session = _make_session(runs=[])
    assert get_session_name(session) == ""


def test_session_name_from_run_input():
    """When no user message, fall back to run input."""
    session = _make_session(runs=[
        {
            "messages": [],
            "input": {"role": "user", "content": "Fallback query"},
        }
    ])
    result = get_session_name(session)
    assert result == "Fallback query"


def test_session_name_team_filters_agent_runs():
    """Team sessions should only use team runs (no agent_id)."""
    session = _make_session(session_type="team", runs=[
        {"agent_id": "agent_1", "messages": [{"role": "user", "content": "Agent run"}]},
        {"messages": [{"role": "user", "content": "Team run query"}]},
    ])
    result = get_session_name(session)
    assert result == "Team run query"


def test_session_name_workflow_string_input():
    session = _make_session(session_type="workflow", runs=[
        {"input": "My workflow input"},
    ])
    assert get_session_name(session) == "My workflow input"


def test_session_name_workflow_dict_input():
    session = _make_session(session_type="workflow", runs=[
        {"input": {"topic": "AI", "style": "formal"}},
    ])
    result = get_session_name(session)
    parsed = json.loads(result)
    assert parsed["topic"] == "AI"


def test_session_name_long_user_message_truncated():
    session = _make_session(runs=[
        {"messages": [{"role": "user", "content": "x" * 200}]},
    ])
    result = get_session_name(session)
    assert len(result) == _SESSION_NAME_MAX_LENGTH
    assert result.endswith("...")


def test_session_name_real_world_knowledge_pollution():
    """The exact scenario the user reported."""
    content = (
        "看看斯贝利单抗的机制是什么\n\n"
        "Use the following references from the knowledge base if it helps:\n"
        "<references>\n"
        '[{"content": "y significant safety signals... (very long)", "name": "doc.pdf"},'
        '{"content": "another huge doc...", "name": "doc2.pdf"}]\n'
        "</references>"
    )
    session = _make_session(runs=[
        {"messages": [{"role": "user", "content": content}]},
    ])
    result = get_session_name(session)
    assert result == "看看斯贝利单抗的机制是什么"
    assert len(result) < 50


def test_session_name_preserves_explicit_name():
    """Explicit session_name should never be modified."""
    long_name = "x" * 500
    session = _make_session(session_data={"session_name": long_name})
    result = get_session_name(session)
    assert result == long_name  # Not truncated


# ============================================================
# extract_input_media — verify not broken
# ============================================================


def test_extract_input_media_basic():
    run_dict = {"input": {"images": ["img1"], "videos": ["vid1"]}}
    result = extract_input_media(run_dict)
    assert result["images"] == ["img1"]
    assert result["videos"] == ["vid1"]
    assert result["audios"] == []
    assert result["files"] == []


def test_extract_input_media_no_input():
    run_dict = {}
    result = extract_input_media(run_dict)
    assert result == {"images": [], "videos": [], "audios": [], "files": []}


def test_extract_input_media_non_dict_input():
    run_dict = {"input": "just a string"}
    result = extract_input_media(run_dict)
    assert result == {"images": [], "videos": [], "audios": [], "files": []}
