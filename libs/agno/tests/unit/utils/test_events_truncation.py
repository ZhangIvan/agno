"""Tests for SSE tool result truncation in events.py."""

import json

from agno.models.response import ToolExecution
from agno.utils.events import (
    _GENERIC_RESULT_THRESHOLD,
    _KNOWLEDGE_RESULT_THRESHOLD,
    _KNOWLEDGE_TOOL_NAMES,
    _MAX_JSON_PARSE_SIZE,
    _TOOL_RESULT_THRESHOLD,
    _format_size,
    _make_summary,
    _summarize_result,
    _tool_event_without_result,
    _truncate_generic_result,
    _truncate_strings,
)

# ============================================================
# _format_size
# ============================================================


def test_format_size_bytes():
    assert _format_size(0) == "0 B"
    assert _format_size(100) == "100 B"
    assert _format_size(1023) == "1023 B"


def test_format_size_kb():
    assert _format_size(1024) == "1.0 KB"
    assert _format_size(5120) == "5.0 KB"
    assert _format_size(1024 * 1024 - 1) == "1024.0 KB"


def test_format_size_mb():
    assert _format_size(1024 * 1024) == "1.0 MB"
    assert _format_size(5 * 1024 * 1024) == "5.0 MB"


# ============================================================
# _truncate_strings
# ============================================================


def test_truncate_strings_short():
    assert _truncate_strings("hello") == "hello"


def test_truncate_strings_long():
    long_str = "a" * 300
    result = _truncate_strings(long_str)
    assert len(result) == 203  # 200 + "..."
    assert result.endswith("...")


def test_truncate_strings_list():
    data = ["short", "a" * 300, "also short"]
    result = _truncate_strings(data)
    assert result[0] == "short"
    assert len(result[1]) == 203
    assert result[2] == "also short"


def test_truncate_strings_nested_dict():
    data = {"key": "a" * 300, "nested": {"inner": "b" * 300}}
    result = _truncate_strings(data)
    assert len(result["key"]) == 203
    assert len(result["nested"]["inner"]) == 203


def test_truncate_strings_depth_limit():
    deep = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": {"j": {"k": "deep"}}}}}}}}}}}
    result = _truncate_strings(deep, max_depth=5)
    # depth 0: outer dict, depth 1: "a", depth 2: "b", depth 3: "c",
    # depth 4: "d", depth 5: "e", depth 6: "f" (>5) => "..."
    assert result["a"]["b"]["c"]["d"]["e"]["f"] == "..."


def test_truncate_strings_preserves_non_string():
    assert _truncate_strings(42) == 42
    assert _truncate_strings(True) is True
    assert _truncate_strings(None) is None
    assert _truncate_strings(3.14) == 3.14


def test_truncate_strings_empty_structures():
    assert _truncate_strings([]) == []
    assert _truncate_strings({}) == {}
    assert _truncate_strings("") == ""


def test_truncate_strings_bool_not_treated_as_int():
    """Bool should pass through, not be treated as int (isinstance(True, int) is True)."""
    result = _truncate_strings([True, False])
    assert result == [True, False]


def test_truncate_strings_custom_max_str():
    result = _truncate_strings("abcdefgh", max_str=5)
    assert result == "abcde..."


# ============================================================
# _make_summary
# ============================================================


def test_make_summary_basic():
    result = json.loads(_make_summary("1.5 KB"))
    assert result["_truncated"] is True
    assert result["original_size"] == "1.5 KB"
    assert "total_items" not in result


def test_make_summary_with_item_count():
    result = json.loads(_make_summary("1.5 KB", item_count=14))
    assert result["total_items"] == 14


def test_make_summary_valid_json():
    """All _make_summary output must be valid JSON."""
    output = _make_summary("50.8 KB", item_count=100)
    parsed = json.loads(output)
    assert isinstance(parsed, dict)


# ============================================================
# _summarize_result (knowledge search)
# ============================================================


def test_summarize_result_small():
    """Below threshold, return as-is."""
    small = "short result"
    assert _summarize_result(small) == small


def test_summarize_result_json_list():
    big_list = json.dumps([{"content": "x" * 50}] * 20)
    result = _summarize_result(big_list)
    parsed = json.loads(result)
    assert parsed["_truncated"] is True
    assert parsed["total_items"] == 20


def test_summarize_result_json_dict():
    result = _summarize_result(json.dumps({"key": "a" * 600}))
    parsed = json.loads(result)
    assert parsed["_truncated"] is True
    assert "total_items" not in parsed


def test_summarize_result_non_json():
    result = _summarize_result("x" * 600)
    parsed = json.loads(result)
    assert parsed["_truncated"] is True


def test_summarize_result_oversized():
    """Result > _MAX_JSON_PARSE_SIZE should get summary without parsing."""
    result = _summarize_result("x" * 60000)
    parsed = json.loads(result)
    assert parsed["_truncated"] is True


def test_summarize_result_exactly_at_threshold():
    """Exactly at threshold should pass through."""
    result = "x" * _KNOWLEDGE_RESULT_THRESHOLD
    assert _summarize_result(result) == result


def test_summarize_result_one_over_threshold():
    """One char over threshold should trigger summary."""
    result = _summarize_result("x" * (_KNOWLEDGE_RESULT_THRESHOLD + 1))
    parsed = json.loads(result)
    assert parsed["_truncated"] is True


def test_summarize_result_json_primitive_string():
    """A JSON string value like '"hello"' is not a list."""
    result = _summarize_result(json.dumps("x" * 600))
    parsed = json.loads(result)
    assert parsed["_truncated"] is True


def test_summarize_result_empty_list():
    result = _summarize_result("[]")
    # Empty list is <= threshold (2 chars)
    assert _summarize_result("[]") == "[]"


def test_summarize_result_chinese():
    """Chinese text with multibyte chars."""
    chinese = "斯贝利单抗的机制" * 50  # ~400 chars, under 500
    assert _summarize_result(chinese) == chinese


# ============================================================
# _truncate_generic_result
# ============================================================


def test_generic_result_small():
    """Below threshold, return as-is."""
    small = "short result"
    assert _truncate_generic_result(small) == small


def test_generic_result_json_list_few_items():
    """List with fewer than max_items still gets _summary wrapper."""
    data = [{"text": "item1"}, {"text": "item2"}]
    result = json.loads(_truncate_generic_result(json.dumps(data) + " " * 1000))
    assert result["_summary"]["_truncated"] is True
    assert result["_summary"]["shown_items"] == 2
    assert result["_summary"]["total_items"] == 2
    assert len(result["preview"]) == 2


def test_generic_result_json_list_many_items():
    data = [{"text": f"item{i}" * 50} for i in range(20)]  # pad to exceed threshold
    result = json.loads(_truncate_generic_result(json.dumps(data)))
    assert result["_summary"]["total_items"] == 20
    assert result["_summary"]["shown_items"] == 5
    assert len(result["preview"]) == 5


def test_generic_result_json_dict():
    data = {"key1": "a" * 300, "key2": "b" * 300}
    result = _truncate_generic_result(json.dumps(data) + " " * 1000)
    parsed = json.loads(result)
    assert "key1" in parsed
    assert len(parsed["key1"]) == 203  # truncated


def test_generic_result_non_json():
    result = _truncate_generic_result("x" * 2000)
    parsed = json.loads(result)
    assert parsed["_truncated"] is True


def test_generic_result_oversized():
    result = _truncate_generic_result("x" * 60000)
    parsed = json.loads(result)
    assert parsed["_truncated"] is True


def test_generic_result_exactly_max_items():
    """Exactly 5 items (default max_items) — should still have _summary."""
    data = [{"text": f"item{i}"} for i in range(5)]
    raw = json.dumps(data) + " " * 1000  # pad to exceed threshold
    result = json.loads(_truncate_generic_result(raw))
    assert result["_summary"]["_truncated"] is True
    assert result["_summary"]["total_items"] == 5
    assert result["_summary"]["shown_items"] == 5


def test_generic_result_truncated_strings_in_preview():
    """Strings in preview should be truncated to 200 chars."""
    data = [{"text": "a" * 300}]
    raw = json.dumps(data) + " " * 1000
    result = json.loads(_truncate_generic_result(raw))
    assert len(result["preview"][0]["text"]) == 203


def test_generic_result_empty_structures():
    assert _truncate_generic_result("[]") == "[]"
    assert _truncate_generic_result("{}") == "{}"


# ============================================================
# _tool_event_without_result
# ============================================================


def _make_tool(result=None, tool_name="test_tool"):
    return ToolExecution(tool_name=tool_name, tool_call_id="call_123", result=result)


def test_tool_event_none_result():
    """None result (started events) should return original."""
    tool = _make_tool(result=None)
    result = _tool_event_without_result(tool)
    assert result is tool  # same object, no copy


def test_tool_event_small_result():
    """Small result should return original."""
    tool = _make_tool(result="short")
    result = _tool_event_without_result(tool)
    assert result is tool


def test_tool_event_knowledge_search():
    """Knowledge search tool should get aggressive summary."""
    big_result = json.dumps([{"content": "x" * 50}] * 20)
    tool = _make_tool(result=big_result, tool_name="search_knowledge_base")
    result = _tool_event_without_result(tool)
    assert result is not tool  # new copy
    assert result.tool_name == "search_knowledge_base"
    assert result.tool_call_id == "call_123"
    parsed = json.loads(result.result)
    assert parsed["_truncated"] is True
    assert parsed["total_items"] == 20


def test_tool_event_generic_tool():
    """Non-knowledge tool should get structural truncation."""
    big_result = json.dumps([{"text": f"item{i}" * 50} for i in range(10)])
    tool = _make_tool(result=big_result, tool_name="web_search")
    result = _tool_event_without_result(tool)
    assert result is not tool
    assert result.tool_name == "web_search"
    parsed = json.loads(result.result)
    assert parsed["_summary"]["_truncated"] is True


def test_tool_event_preserves_other_fields():
    """Truncation should preserve all other ToolExecution fields."""
    tool = ToolExecution(
        tool_name="test",
        tool_call_id="call_123",
        result="x" * 600,
        tool_call_error=None,
        child_run_id="child_456",
        metrics={"tokens": 100},
    )
    result = _tool_event_without_result(tool)
    assert result.child_run_id == "child_456"
    assert result.metrics == {"tokens": 100}
    assert result.tool_call_error is None


def test_tool_event_original_unchanged():
    """Original tool must NOT be mutated."""
    big_result = json.dumps([{"content": "doc"}] * 20)
    tool = _make_tool(result=big_result, tool_name="search_knowledge_base")
    original_result = tool.result
    _tool_event_without_result(tool)
    assert tool.result == original_result  # unchanged


def test_tool_event_none_tool_name():
    """None tool_name should be treated as generic."""
    tool = _make_tool(result="x" * 600, tool_name=None)
    result = _tool_event_without_result(tool)
    assert result is not tool


def test_tool_event_knowledge_tool_names_set():
    """Verify the knowledge tool names constant."""
    assert "search_knowledge_base" in _KNOWLEDGE_TOOL_NAMES
    assert len(_KNOWLEDGE_TOOL_NAMES) == 1


# ============================================================
# All outputs must be valid JSON when truncation is triggered
# ============================================================


def test_all_summarize_outputs_valid_json():
    """Every _summarize_result output > threshold must be parseable JSON."""
    cases = [
        json.dumps([{"c": "d"}] * 20),
        json.dumps({"key": "val"}),
        "plain text " * 100,
        "x" * 60000,
        json.dumps("a string value"),
        json.dumps(42),
        json.dumps(True),
        json.dumps(None),
    ]
    for case in cases:
        if len(case) <= _KNOWLEDGE_RESULT_THRESHOLD:
            continue
        result = _summarize_result(case)
        json.loads(result)  # should not raise


def test_all_generic_outputs_valid_json():
    """Every _truncate_generic_result output > threshold must be parseable JSON."""
    cases = [
        json.dumps([{"c": "d"}] * 20),
        json.dumps({"key": "val" * 200}),
        "plain text " * 200,
        "x" * 60000,
        json.dumps([1, 2, 3, 4, 5]),
    ]
    for case in cases:
        if len(case) <= _GENERIC_RESULT_THRESHOLD:
            continue
        result = _truncate_generic_result(case)
        json.loads(result)  # should not raise
