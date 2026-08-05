from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, MetaData, String, Table
from sqlalchemy.dialects import postgresql

from agno.exceptions import VectorDbSearchError
from agno.vectordb.distance import Distance
from agno.vectordb.pgvector import PgVector
from agno.vectordb.search import SearchType


def _make_db(
    *,
    strict_search: bool = False,
    statement_timeout_ms: Optional[int] = None,
    reranker=None,
) -> PgVector:
    engine = MagicMock()
    engine.url = "postgresql+psycopg://runtime"

    embedder = MagicMock()
    embedder.dimensions = 3
    embedder.get_embedding.return_value = [0.1, 0.2, 0.3]

    metadata = MetaData(schema="ai")
    table = Table(
        "strict_vectors",
        metadata,
        Column("id", String, primary_key=True),
        Column("name", String),
        Column("meta_data", postgresql.JSONB),
        Column("content", String),
        Column("embedding", Vector(3)),
        Column("usage", postgresql.JSONB),
    )

    with (
        patch("agno.vectordb.pgvector.pgvector.scoped_session"),
        patch.object(PgVector, "get_table", return_value=table),
    ):
        db = PgVector(
            table_name="strict_vectors",
            db_engine=engine,
            embedder=embedder,
            reranker=reranker,
            strict_search=strict_search,
            statement_timeout_ms=statement_timeout_ms,
        )
    db.vector_index = None
    return db


def _set_session(db: PgVector, *, rows=None, error: Optional[Exception] = None) -> MagicMock:
    sess = MagicMock()
    if error is not None:
        sess.execute.side_effect = error
    else:
        result = MagicMock()
        result.fetchall.return_value = rows or []
        sess.execute.return_value = result

    session_context = MagicMock()
    session_context.__enter__.return_value = sess
    db.Session = MagicMock(return_value=session_context)
    return sess


def test_default_strict_options_preserve_compatibility():
    db = _make_db()

    assert db.strict_search is False
    assert db.statement_timeout_ms is None


@pytest.mark.parametrize("timeout", [0, -1, True, 1.5, 2_147_483_648])
def test_statement_timeout_rejects_invalid_values(timeout):
    with pytest.raises(ValueError, match="statement_timeout_ms"):
        _make_db(statement_timeout_ms=timeout)


def test_strict_search_rejects_non_boolean_value():
    with pytest.raises(ValueError, match="strict_search"):
        _make_db(strict_search="true")  # type: ignore[arg-type]


@pytest.mark.parametrize("method_name", ["vector_search", "keyword_search", "hybrid_search", "grep_search"])
def test_default_search_modes_preserve_empty_result_on_database_error(method_name):
    db = _make_db()
    _set_session(db, error=RuntimeError("database unavailable"))
    db.create = MagicMock()

    with patch.object(db, "_ensure_pgtrgm_extension", return_value=None):
        result = getattr(db, method_name)("query")

    assert result == []
    if method_name in {"vector_search", "keyword_search"}:
        db.create.assert_called_once_with()
    else:
        db.create.assert_not_called()


@pytest.mark.parametrize("method_name", ["vector_search", "keyword_search", "hybrid_search", "grep_search"])
def test_strict_search_modes_fail_closed_without_ddl_or_secret_logs(method_name):
    secret = "postgresql://admin:super-secret@database/runtime"
    db = _make_db(strict_search=True)
    _set_session(db, error=RuntimeError(secret))
    db.create = MagicMock()

    with (
        patch.object(db, "_ensure_pgtrgm_extension") as ensure_pgtrgm,
        patch("agno.vectordb.pgvector.pgvector.log_debug") as log_debug,
        patch("agno.vectordb.pgvector.pgvector.log_error") as log_error,
        pytest.raises(VectorDbSearchError, match="^Vector database search failed$") as exc_info,
    ):
        getattr(db, method_name)(f"credential={secret}")

    assert exc_info.value.__suppress_context__ is True
    db.create.assert_not_called()
    if method_name == "grep_search":
        ensure_pgtrgm.assert_not_called()
    rendered_logs = " ".join(str(call) for call in [*log_debug.call_args_list, *log_error.call_args_list])
    assert secret not in rendered_logs


def test_strict_embedding_failure_is_not_converted_to_empty_results():
    secret = "api_key=embedding-secret"
    db = _make_db(strict_search=True)
    db.embedder.get_embedding.side_effect = RuntimeError(secret)
    db.Session = MagicMock()

    with (
        patch("agno.vectordb.pgvector.pgvector.log_error") as log_error,
        pytest.raises(VectorDbSearchError, match="^Vector database search failed$") as exc_info,
    ):
        db.vector_search(secret)

    assert exc_info.value.__suppress_context__ is True
    db.Session.assert_not_called()
    assert secret not in " ".join(str(call) for call in log_error.call_args_list)


def test_strict_reranker_failure_is_sanitized_and_propagated():
    secret = "reranker-token=super-secret"
    reranker = MagicMock()
    reranker.rerank.side_effect = RuntimeError(secret)
    db = _make_db(strict_search=True, reranker=reranker)
    row = SimpleNamespace(
        id="doc-1",
        name="document",
        meta_data={},
        content="content",
        embedding=[0.1, 0.2, 0.3],
        usage={},
        distance=0.1,
    )
    _set_session(db, rows=[row])

    with (
        patch("agno.vectordb.pgvector.pgvector.log_error") as log_error,
        pytest.raises(VectorDbSearchError, match="^Vector database search failed$") as exc_info,
    ):
        db.vector_search("query")

    assert exc_info.value.__suppress_context__ is True
    assert secret not in " ".join(str(call) for call in log_error.call_args_list)


@pytest.mark.asyncio
async def test_strict_async_search_propagates_domain_error():
    db = _make_db(strict_search=True)
    db.search_type = SearchType.hybrid
    _set_session(db, error=RuntimeError("async database secret"))

    with pytest.raises(VectorDbSearchError, match="^Vector database search failed$"):
        await db.async_search("query")


@pytest.mark.parametrize("method_name", ["vector_search", "keyword_search", "hybrid_search", "grep_search"])
def test_statement_timeout_is_applied_to_every_strict_database_query(method_name):
    db = _make_db(strict_search=True, statement_timeout_ms=250)
    sess = _set_session(db)

    with patch.object(db, "_ensure_pgtrgm_extension") as ensure_pgtrgm:
        assert getattr(db, method_name)("query") == []

    if method_name == "grep_search":
        ensure_pgtrgm.assert_not_called()
    assert len(sess.execute.call_args_list) == 2
    timeout_call = sess.execute.call_args_list[0]
    assert "set_config('statement_timeout'" in str(timeout_call.args[0])
    assert timeout_call.args[1] == {"statement_timeout": "250ms"}


def test_statement_timeout_is_ignored_outside_strict_mode():
    db = _make_db(statement_timeout_ms=250)
    sess = _set_session(db)

    assert db.vector_search("query") == []

    assert len(sess.execute.call_args_list) == 1
    assert "set_config('statement_timeout'" not in str(sess.execute.call_args_list[0].args[0])


def test_strict_mode_blocks_explicit_ddl_entrypoints():
    db = _make_db(strict_search=True)
    db.table_exists = MagicMock(return_value=False)
    db._create_vector_index = MagicMock()

    for operation in (db.create, db.drop, db.optimize):
        with pytest.raises(VectorDbSearchError, match="Database DDL is disabled"):
            operation()

    db.table_exists.assert_not_called()
    db._create_vector_index.assert_not_called()


def test_strict_pgtrgm_setup_is_a_noop():
    db = _make_db(strict_search=True)
    db.Session = MagicMock()

    db._ensure_pgtrgm_extension()

    db.Session.assert_not_called()


def test_strict_invalid_search_type_fails_closed():
    db = _make_db(strict_search=True)
    db.search_type = "unsupported"  # type: ignore[assignment]
    db.Session = MagicMock()

    with pytest.raises(VectorDbSearchError, match="^Vector database search failed$"):
        db.search("query")

    db.Session.assert_not_called()


def test_strict_unknown_distance_fails_closed():
    db = _make_db(strict_search=True)
    db.distance = "unsupported"  # type: ignore[assignment]
    db.Session = MagicMock()

    with pytest.raises(VectorDbSearchError, match="^Vector database search failed$"):
        db.vector_search("query")

    db.Session.assert_not_called()
    assert db.distance != Distance.cosine
