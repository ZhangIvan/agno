from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agno.exceptions import KnowledgeSearchError, VectorDbSearchError
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.search import SearchType


def _mock_vector_db(*, exists: bool = True) -> MagicMock:
    vector_db = MagicMock()
    vector_db.exists.return_value = exists
    vector_db.search_type = SearchType.vector
    vector_db.strict_search = False
    return vector_db


def test_default_initialization_preserves_exists_and_create_behavior():
    vector_db = _mock_vector_db(exists=False)

    knowledge = Knowledge(vector_db=vector_db)

    assert knowledge.strict_retrieval is False
    vector_db.exists.assert_called_once_with()
    vector_db.create.assert_called_once_with()
    assert vector_db.strict_search is False


def test_strict_initialization_performs_no_vector_db_io():
    vector_db = _mock_vector_db(exists=False)

    knowledge = Knowledge(vector_db=vector_db, strict_retrieval=True)

    assert knowledge.strict_retrieval is True
    assert vector_db.strict_search is True
    vector_db.exists.assert_not_called()
    vector_db.create.assert_not_called()


def test_default_search_preserves_empty_result_on_error():
    vector_db = _mock_vector_db()
    vector_db.search.side_effect = RuntimeError("database unavailable")
    knowledge = Knowledge(vector_db=vector_db)

    assert knowledge.search("query") == []


def test_strict_search_raises_sanitized_domain_error_without_secret_logs():
    secret = "postgresql://admin:super-secret@database/runtime"
    vector_db = _mock_vector_db()
    vector_db.search.side_effect = RuntimeError(secret)
    knowledge = Knowledge(vector_db=vector_db, strict_retrieval=True)

    with (
        patch("agno.knowledge.knowledge.log_debug") as log_debug,
        patch("agno.knowledge.knowledge.log_error") as log_error,
        pytest.raises(KnowledgeSearchError, match="^Knowledge search failed$") as exc_info,
    ):
        knowledge.search(f"credential={secret}")

    assert exc_info.value.__suppress_context__ is True
    rendered_logs = " ".join(str(call) for call in [*log_debug.call_args_list, *log_error.call_args_list])
    assert secret not in rendered_logs
    assert "exc_info" not in rendered_logs


@pytest.mark.asyncio
async def test_strict_async_search_raises_sanitized_domain_error():
    secret = "password=async-secret"
    vector_db = _mock_vector_db()
    vector_db.async_search = AsyncMock(side_effect=RuntimeError(secret))
    knowledge = Knowledge(vector_db=vector_db, strict_retrieval=True)

    with (
        patch("agno.knowledge.knowledge.log_error") as log_error,
        pytest.raises(KnowledgeSearchError, match="^Knowledge search failed$") as exc_info,
    ):
        await knowledge.asearch(secret)

    assert exc_info.value.__suppress_context__ is True
    assert secret not in " ".join(str(call) for call in log_error.call_args_list)
    vector_db.search.assert_not_called()


@pytest.mark.asyncio
async def test_default_async_search_preserves_sync_fallback():
    vector_db = _mock_vector_db()
    vector_db.async_search = AsyncMock(side_effect=NotImplementedError)
    vector_db.search.return_value = []
    knowledge = Knowledge(vector_db=vector_db)

    assert await knowledge.asearch("query") == []
    vector_db.search.assert_called_once_with(query="query", limit=10, filters=None)


def test_strict_search_without_vector_db_fails_closed():
    knowledge = Knowledge(strict_retrieval=True)

    with pytest.raises(KnowledgeSearchError, match="^Knowledge search failed$"):
        knowledge.search("query")


def test_strict_invalid_search_type_is_wrapped_without_calling_backend():
    vector_db = _mock_vector_db()
    knowledge = Knowledge(vector_db=vector_db, strict_retrieval=True)

    with pytest.raises(KnowledgeSearchError, match="^Knowledge search failed$"):
        knowledge.search("query", search_type="unsupported")

    vector_db.search.assert_not_called()


def test_opt_in_vector_db_domain_error_is_not_swallowed_by_default_knowledge():
    vector_db = _mock_vector_db()
    vector_db.search.side_effect = VectorDbSearchError()
    knowledge = Knowledge(vector_db=vector_db)

    with pytest.raises(VectorDbSearchError, match="^Vector database search failed$"):
        knowledge.search("query")
