"""Unit tests for cosmos_odm.errors (exception hierarchy)."""

import pytest

from cosmos_odm.errors import (
    BadQuery,
    ConditionalCheckFailed,
    CosmosODMError,
    CrossPartitionDisallowed,
    FullTextIndexMissing,
    NotFound,
    PartitionKeyMismatch,
    ThroughputExceeded,
    VectorIndexMissing,
)


class TestCosmosODMError:
    def test_stores_attributes(self):
        err = CosmosODMError(
            "msg", status_code=500, activity_id="act-1", details={"k": "v"}
        )
        assert str(err) == "msg"
        assert err.status_code == 500
        assert err.activity_id == "act-1"
        assert err.details == {"k": "v"}

    def test_details_default(self):
        err = CosmosODMError("msg")
        assert err.details == {}


class TestSubclasses:
    @pytest.mark.parametrize(
        "cls",
        [
            NotFound,
            BadQuery,
            ConditionalCheckFailed,
            CrossPartitionDisallowed,
            PartitionKeyMismatch,
        ],
    )
    def test_inherits_cosmos_odm_error(self, cls):
        err = cls("test error", status_code=400)
        assert isinstance(err, CosmosODMError)
        assert str(err) == "test error"

    @pytest.mark.parametrize(
        "cls",
        [
            NotFound,
            BadQuery,
            ConditionalCheckFailed,
            CrossPartitionDisallowed,
            PartitionKeyMismatch,
        ],
    )
    def test_catchable_as_base(self, cls):
        with pytest.raises(CosmosODMError):
            raise cls("boom")


class TestThroughputExceeded:
    def test_stores_retry_after_ms(self):
        err = ThroughputExceeded("rate limited", retry_after_ms=1500, status_code=429)
        assert err.retry_after_ms == 1500
        assert err.status_code == 429
        assert isinstance(err, CosmosODMError)


class TestVectorIndexMissing:
    def test_stores_vector_path(self):
        err = VectorIndexMissing("no index", vector_path="/embedding")
        assert err.vector_path == "/embedding"
        assert isinstance(err, CosmosODMError)

    def test_remediation_message(self):
        err = VectorIndexMissing("no index", vector_path="/embedding")
        assert "/embedding" in err.remediation
        assert "ensure_indexes" in err.remediation


class TestFullTextIndexMissing:
    def test_stores_text_paths(self):
        err = FullTextIndexMissing("no index", text_paths=["/title", "/content"])
        assert err.text_paths == ["/title", "/content"]
        assert isinstance(err, CosmosODMError)

    def test_remediation_message(self):
        err = FullTextIndexMissing("no index", text_paths=["/title"])
        assert "/title" in err.remediation
        assert "ensure_indexes" in err.remediation
