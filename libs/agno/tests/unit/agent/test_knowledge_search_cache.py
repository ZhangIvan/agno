"""Tests for multi-query knowledge search and deduplication."""

from unittest.mock import MagicMock, patch

from agno.agent._default_tools import create_knowledge_search_tool


def _make_agent():
    agent = MagicMock()
    agent.knowledge = MagicMock()
    agent.knowledge.use_page_images = False
    agent.knowledge_retriever = None
    agent.enable_agentic_knowledge_filters = False
    agent.lean_references = True
    agent.references_format = "json"
    agent.search_knowledge = True
    return agent


def _call_tool(tool, queries):
    """Call the search_knowledge_base entrypoint with a queries list."""
    return tool.entrypoint(queries=queries)


# ============================================================
# Multiple queries in one call
# ============================================================


def test_multiple_queries_combined():
    agent = _make_agent()
    queries_searched = []

    def mock_get_docs(*args, **kwargs):
        q = kwargs.get("query")
        queries_searched.append(q)
        return [{"content": f"doc-for-{q}"}]

    with patch("agno.agent._messages.get_relevant_docs_from_knowledge", side_effect=mock_get_docs):
        tool = create_knowledge_search_tool(agent)
        result = _call_tool(tool, ["query-a", "query-b"])

    assert queries_searched == ["query-a", "query-b"]
    assert "doc-for-query-a" in result
    assert "doc-for-query-b" in result


# ============================================================
# Dedup across queries in the same call
# ============================================================


def test_duplicate_docs_across_queries_are_deduped():
    agent = _make_agent()
    shared_doc = {"content": "shared content"}
    call_count = 0

    def mock_get_docs(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return [shared_doc, {"content": "unique-1"}]
        return [shared_doc, {"content": "unique-2"}]

    with patch("agno.agent._messages.get_relevant_docs_from_knowledge", side_effect=mock_get_docs):
        tool = create_knowledge_search_tool(agent)
        result = _call_tool(tool, ["query-a", "query-b"])

    assert "shared content" in result
    assert "unique-1" in result
    assert "unique-2" in result
    # shared doc appears only once
    assert result.count("shared content") == 1


# ============================================================
# Dedup across separate tool calls
# ============================================================


def test_cross_call_dedup():
    agent = _make_agent()
    shared_doc = {"content": "shared-content"}

    def mock_get_docs(*args, **kwargs):
        q = kwargs.get("query")
        return [shared_doc, {"content": f"unique-for-{q}"}]

    with patch("agno.agent._messages.get_relevant_docs_from_knowledge", side_effect=mock_get_docs):
        tool = create_knowledge_search_tool(agent)
        r1 = _call_tool(tool, ["query-a"])
        r2 = _call_tool(tool, ["query-b"])

    # shared-content appears in r1 but is suppressed in r2
    assert "shared-content" in r1
    assert "unique-for-query-a" in r1
    assert "shared-content" not in r2
    assert "unique-for-query-b" in r2


# ============================================================
# Single query in list still works
# ============================================================


def test_single_query_in_list():
    agent = _make_agent()

    def mock_get_docs(*args, **kwargs):
        return [{"content": "only-doc"}]

    with patch("agno.agent._messages.get_relevant_docs_from_knowledge", side_effect=mock_get_docs):
        tool = create_knowledge_search_tool(agent)
        result = _call_tool(tool, ["single-query"])

    assert "only-doc" in result


# ============================================================
# No docs found
# ============================================================


def test_no_docs_returns_not_found():
    agent = _make_agent()

    def mock_get_docs(*args, **kwargs):
        return None

    with patch("agno.agent._messages.get_relevant_docs_from_knowledge", side_effect=mock_get_docs):
        tool = create_knowledge_search_tool(agent)
        result = _call_tool(tool, ["empty-query"])

    assert result == "No documents found"


# ============================================================
# Partial failure — one query fails, others succeed
# ============================================================


def test_partial_failure_returns_remaining_results():
    agent = _make_agent()
    call_count = 0

    def mock_get_docs(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("search error")
        return [{"content": "doc-from-second"}]

    with patch("agno.agent._messages.get_relevant_docs_from_knowledge", side_effect=mock_get_docs):
        tool = create_knowledge_search_tool(agent)
        result = _call_tool(tool, ["fail-query", "ok-query"])

    assert "doc-from-second" in result


# ============================================================
# Dedup set is bounded
# ============================================================


def test_dedup_set_is_bounded():
    agent = _make_agent()

    def mock_get_docs(*args, **kwargs):
        q = kwargs.get("query")
        return [{"content": f"doc-{q}"}]

    with patch("agno.agent._messages.get_relevant_docs_from_knowledge", side_effect=mock_get_docs):
        tool = create_knowledge_search_tool(agent)
        for i in range(25):
            _call_tool(tool, [f"q-{i}"])

    # The tool still works after exceeding _MAX_DOC_HASHES
    with patch("agno.agent._messages.get_relevant_docs_from_knowledge", return_value=[{"content": "new-doc"}]):
        result = _call_tool(tool, ["fresh-query"])
    assert "new-doc" in result
