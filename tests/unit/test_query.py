"""Unit tests for cosmos_odm.query (QueryBuilder, FindQuery, BulkWriter)."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from cosmos_odm.model import PK, ETag
from cosmos_odm.query import FindQuery, BulkWriter

from .conftest import SampleDoc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_collection():
    """Return a mock Collection suitable for QueryBuilder / FindQuery."""
    col = MagicMock()
    col.async_container = AsyncMock()
    return col


# ---------------------------------------------------------------------------
# QueryBuilder / FindQuery SQL generation
# ---------------------------------------------------------------------------

class TestQueryBuilderSQL:
    def test_basic_select(self):
        q = FindQuery(_mock_collection())
        assert q._build_sql() == "SELECT * FROM c"

    def test_where_adds_condition(self):
        q = FindQuery(_mock_collection())
        q.where("c.status = @status", status="active")
        sql = q._build_sql()
        assert "WHERE" in sql
        assert "@param0" in sql
        assert q._parameters["param0"] == "active"

    def test_multiple_where_joined_by_and(self):
        q = FindQuery(_mock_collection())
        q.where("c.a = @a", a=1).where("c.b = @b", b=2)
        sql = q._build_sql()
        assert sql.count("AND") == 1

    def test_order_by_ascending(self):
        q = FindQuery(_mock_collection())
        q.order_by("name", ascending=True)
        sql = q._build_sql()
        assert "ORDER BY c.name ASC" in sql

    def test_order_by_descending(self):
        q = FindQuery(_mock_collection())
        q.order_by("name", ascending=False)
        sql = q._build_sql()
        assert "ORDER BY c.name DESC" in sql

    def test_skip_and_limit(self):
        q = FindQuery(_mock_collection())
        q.skip(10).limit(20)
        sql = q._build_sql()
        assert "OFFSET 10 LIMIT 20" in sql

    def test_limit_only(self):
        q = FindQuery(_mock_collection())
        q.limit(5)
        sql = q._build_sql()
        assert "OFFSET 0 LIMIT 5" in sql

    def test_combined_where_order_limit(self):
        q = FindQuery(_mock_collection())
        q.where("c.active = @a", a=True).order_by("created_at", ascending=False).limit(10)
        sql = q._build_sql()
        assert "WHERE" in sql
        assert "ORDER BY" in sql
        assert "LIMIT 10" in sql

    def test_parameters_use_param_naming(self):
        q = FindQuery(_mock_collection())
        q.where("c.x = @x", x=1)
        q.where("c.y = @y", y=2)
        assert "param0" in q._parameters
        assert "param1" in q._parameters
        # No string interpolation – values are in _parameters dict
        assert q._parameters["param0"] == 1
        assert q._parameters["param1"] == 2


# ---------------------------------------------------------------------------
# BulkWriter
# ---------------------------------------------------------------------------

class TestBulkWriter:
    def test_insert_adds_operation(self):
        col = _mock_collection()
        bw = BulkWriter(col)
        doc = SampleDoc(category=PK("a"), title="t")
        bw.insert(doc)
        assert len(bw._operations) == 1
        assert bw._operations[0]["operation"] == "create"

    def test_upsert_adds_operation(self):
        col = _mock_collection()
        bw = BulkWriter(col)
        doc = SampleDoc(category=PK("a"), title="t")
        bw.upsert(doc)
        assert bw._operations[0]["operation"] == "upsert"

    def test_replace_adds_operation(self):
        col = _mock_collection()
        bw = BulkWriter(col)
        doc = SampleDoc(category=PK("a"), title="t", etag=ETag("e1"))
        bw.replace(doc)
        assert bw._operations[0]["operation"] == "replace"
        assert bw._operations[0]["etag"] == "e1"

    def test_delete_adds_operation(self):
        col = _mock_collection()
        bw = BulkWriter(col)
        bw.delete("pk_val", "id_val")
        assert bw._operations[0]["operation"] == "delete"
        assert bw._operations[0]["item_id"] == "id_val"

    async def test_execute_runs_all(self):
        col = _mock_collection()
        col.async_container.create_item.return_value = {"id": "1"}
        col.async_container.upsert_item.return_value = {"id": "2"}

        bw = BulkWriter(col, max_concurrency=2)
        doc1 = SampleDoc(category=PK("a"), title="t1")
        doc2 = SampleDoc(category=PK("b"), title="t2")
        bw.insert(doc1)
        bw.upsert(doc2)

        results = await bw.execute()
        assert len(results) == 2
        assert all(r["success"] for r in results)

    async def test_execute_empty_returns_empty(self):
        col = _mock_collection()
        bw = BulkWriter(col)
        results = await bw.execute()
        assert results == []

    def test_concurrency_default(self):
        col = _mock_collection()
        bw = BulkWriter(col)
        assert bw.max_concurrency == 10

    def test_concurrency_custom(self):
        col = _mock_collection()
        bw = BulkWriter(col, max_concurrency=5)
        assert bw.max_concurrency == 5
