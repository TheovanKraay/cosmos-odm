"""Unit tests for cosmos_odm.collection (Collection)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from cosmos_odm.collection import Collection
from cosmos_odm.errors import (
    BadQuery,
    ConditionalCheckFailed,
    CosmosODMError,
    CrossPartitionDisallowed,
    NotFound,
    ThroughputExceeded,
)
from cosmos_odm.model import PK, ETag
from cosmos_odm.query import FindQuery

from .conftest import SampleDoc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_collection() -> tuple[Collection, AsyncMock]:
    """Create a Collection with a mocked async_container."""
    manager = MagicMock()
    mock_container = AsyncMock()
    manager.get_async_container.return_value = mock_container
    col = Collection(
        document_type=SampleDoc,
        database_name="testdb",
        client_manager=manager,
    )
    return col, mock_container


def _cosmos_response(doc_dict: dict) -> dict:
    """Return a dict that looks like a Cosmos response for SampleDoc."""
    base = {
        "id": "abc",
        "category": "books",
        "title": "T",
        "content": "",
        "score": 0.0,
        "active": True,
        "tags": [],
        "metadata": {},
        "embedding": [],
        "schema_version": 1,
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
        "etag": "etag-1",
    }
    base.update(doc_dict)
    return base


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

class TestCollectionInit:
    def test_reads_container_settings(self):
        col, _ = _make_collection()
        assert col._container_settings.name == "test_items"
        assert col.container_name == "test_items"


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

class TestGet:
    async def test_get_returns_deserialized_doc(self):
        col, container = _make_collection()
        container.read_item.return_value = _cosmos_response({"title": "Hello"})

        doc = await col.get("books", "abc")
        container.read_item.assert_awaited_once_with(item="abc", partition_key="books")
        assert isinstance(doc, SampleDoc)
        assert doc.title == "Hello"

    async def test_get_unwraps_pk_wrapper(self):
        col, container = _make_collection()
        container.read_item.return_value = _cosmos_response({})

        await col.get(PK("books"), "abc")
        container.read_item.assert_awaited_once_with(item="abc", partition_key="books")

    async def test_get_raises_not_found(self):
        col, container = _make_collection()

        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        container.read_item.side_effect = CosmosResourceNotFoundError(
            status_code=404, message="Not found"
        )

        with pytest.raises(NotFound):
            await col.get("books", "missing")


# ---------------------------------------------------------------------------
# create / replace / upsert
# ---------------------------------------------------------------------------

class TestCRUD:
    async def test_create_calls_create_item(self):
        col, container = _make_collection()
        container.create_item.return_value = _cosmos_response({"title": "New"})

        doc = SampleDoc(category=PK("books"), title="New")
        result = await col.create(doc)

        container.create_item.assert_awaited_once()
        assert isinstance(result, SampleDoc)

    async def test_replace_calls_replace_item(self):
        col, container = _make_collection()
        container.replace_item.return_value = _cosmos_response({"title": "Updated"})

        doc = SampleDoc(id="abc", category=PK("books"), title="Updated")
        result = await col.replace(doc)

        container.replace_item.assert_awaited_once()
        assert result.title == "Updated"

    async def test_replace_with_if_match(self):
        col, container = _make_collection()
        container.replace_item.return_value = _cosmos_response({})

        doc = SampleDoc(id="abc", category=PK("books"), title="U")
        await col.replace(doc, if_match="etag-1")

        call_kwargs = container.replace_item.call_args
        assert call_kwargs.kwargs.get("etag") == "etag-1"
        assert call_kwargs.kwargs.get("match_condition") == "IfMatch"

    async def test_upsert_calls_upsert_item(self):
        col, container = _make_collection()
        container.upsert_item.return_value = _cosmos_response({})

        doc = SampleDoc(category=PK("books"), title="U")
        await col.upsert(doc)

        container.upsert_item.assert_awaited_once()


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

class TestDelete:
    async def test_delete_calls_delete_item(self):
        col, container = _make_collection()

        await col.delete("books", "abc")
        container.delete_item.assert_awaited_once_with(item="abc", partition_key="books")

    async def test_delete_with_if_match(self):
        col, container = _make_collection()

        await col.delete("books", "abc", if_match="etag-1")
        call_kwargs = container.delete_item.call_args
        assert call_kwargs.kwargs.get("etag") == "etag-1"

    async def test_delete_raises_not_found(self):
        col, container = _make_collection()

        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        container.delete_item.side_effect = CosmosResourceNotFoundError(
            status_code=404, message="Not found"
        )

        with pytest.raises(NotFound):
            await col.delete("books", "missing")


# ---------------------------------------------------------------------------
# delete_document
# ---------------------------------------------------------------------------

class TestDeleteDocument:
    async def test_delete_document_passes_if_match(self):
        col, container = _make_collection()

        doc = SampleDoc(id="abc", category=PK("books"), title="T", etag=ETag("e1"))
        await col.delete_document(doc)

        call_kwargs = container.delete_item.call_args
        assert call_kwargs.kwargs.get("etag") == "e1"

    async def test_delete_document_ignore_etag(self):
        col, container = _make_collection()

        doc = SampleDoc(id="abc", category=PK("books"), title="T", etag=ETag("e1"))
        await col.delete_document(doc, ignore_etag=True)

        call_kwargs = container.delete_item.call_args
        assert "etag" not in call_kwargs.kwargs


# ---------------------------------------------------------------------------
# _handle_cosmos_exception
# ---------------------------------------------------------------------------

class TestHandleCosmosException:
    def _make_exc(self, status_code, message="err"):
        exc = MagicMock()
        exc.status_code = status_code
        exc.__str__ = lambda s: message
        exc.activity_id = "act-1"
        return exc

    def test_404_raises_not_found(self):
        col, _ = _make_collection()
        with pytest.raises(NotFound):
            col._handle_cosmos_exception(self._make_exc(404))

    def test_409_raises_conditional_check_failed(self):
        col, _ = _make_collection()
        with pytest.raises(ConditionalCheckFailed):
            col._handle_cosmos_exception(self._make_exc(409))

    def test_412_raises_conditional_check_failed(self):
        col, _ = _make_collection()
        with pytest.raises(ConditionalCheckFailed):
            col._handle_cosmos_exception(self._make_exc(412))

    def test_429_raises_throughput_exceeded(self):
        col, _ = _make_collection()
        exc = self._make_exc(429)
        exc.retry_after_milliseconds = 1000
        with pytest.raises(ThroughputExceeded):
            col._handle_cosmos_exception(exc)

    def test_400_raises_bad_query(self):
        col, _ = _make_collection()
        with pytest.raises(BadQuery):
            col._handle_cosmos_exception(self._make_exc(400, "syntax error"))

    def test_400_cross_partition_raises(self):
        col, _ = _make_collection()
        with pytest.raises(CrossPartitionDisallowed):
            col._handle_cosmos_exception(
                self._make_exc(400, "Cross partition query is required")
            )

    def test_other_raises_cosmos_odm_error(self):
        col, _ = _make_collection()
        with pytest.raises(CosmosODMError):
            col._handle_cosmos_exception(self._make_exc(500))


# ---------------------------------------------------------------------------
# _extract_ru_metrics
# ---------------------------------------------------------------------------

class TestExtractRUMetrics:
    def test_extracts_from_headers(self):
        col, _ = _make_collection()
        headers = {
            "x-ms-request-charge": "3.5",
            "x-ms-activity-id": "act-123",
            "x-ms-session-token": "tok",
        }
        metrics = col._extract_ru_metrics(headers)
        assert metrics.request_charge == 3.5
        assert metrics.activity_id == "act-123"
        assert metrics.session_token == "tok"


# ---------------------------------------------------------------------------
# find / find_all
# ---------------------------------------------------------------------------

class TestFind:
    def test_find_returns_find_query(self):
        col, _ = _make_collection()
        q = col.find()
        assert isinstance(q, FindQuery)

    def test_find_all_returns_find_query(self):
        col, _ = _make_collection()
        q = col.find_all()
        assert isinstance(q, FindQuery)

    def test_find_with_condition(self):
        col, _ = _make_collection()
        q = col.find("c.status = @status", status="active")
        assert len(q._conditions) == 1
        assert any(v == "active" for v in q._parameters.values())
