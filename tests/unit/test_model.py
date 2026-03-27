"""Unit tests for cosmos_odm.model (Document, PK, ETag, decorators)."""

import uuid
from datetime import datetime, timezone

import pytest

from cosmos_odm.model import Document, PK, ETag, container, embeddings, MergeStrategy
from cosmos_odm.types import ContainerSettings, VectorPolicySpec, VectorIndexSpec, FullTextIndexSpec

from .conftest import SampleDoc


# ---------------------------------------------------------------------------
# Document creation
# ---------------------------------------------------------------------------

class TestDocumentCreation:
    def test_create_with_all_field_types(self):
        doc = SampleDoc(
            category=PK("books"),
            title="Hello",
            content="world",
            score=3.14,
            active=False,
            tags=["a", "b"],
            metadata={"k": 1},
            embedding=[0.1, 0.2, 0.3, 0.4],
        )
        assert doc.title == "Hello"
        assert doc.content == "world"
        assert doc.score == 3.14
        assert doc.active is False
        assert doc.tags == ["a", "b"]
        assert doc.metadata == {"k": 1}
        assert doc.embedding == [0.1, 0.2, 0.3, 0.4]

    def test_auto_generated_id_is_uuid(self):
        doc = SampleDoc(category=PK("a"), title="t")
        parsed = uuid.UUID(doc.id)
        assert str(parsed) == doc.id

    def test_custom_id(self):
        doc = SampleDoc(id="custom-123", category=PK("a"), title="t")
        assert doc.id == "custom-123"

    def test_schema_version_defaults_to_1(self):
        doc = SampleDoc(category=PK("a"), title="t")
        assert doc.schema_version == 1

    def test_timestamps_set_on_creation(self):
        before = datetime.now(timezone.utc)
        doc = SampleDoc(category=PK("a"), title="t")
        after = datetime.now(timezone.utc)
        assert before <= doc.created_at <= after
        assert before <= doc.updated_at <= after


# ---------------------------------------------------------------------------
# ID validation
# ---------------------------------------------------------------------------

class TestIdValidation:
    def test_id_max_1023_bytes(self):
        long_id = "x" * 1024
        with pytest.raises(ValueError, match="1023 bytes"):
            SampleDoc(id=long_id, category=PK("a"), title="t")

    def test_id_no_forward_slash(self):
        with pytest.raises(ValueError, match="must not contain"):
            SampleDoc(id="a/b", category=PK("a"), title="t")

    def test_id_no_backslash(self):
        with pytest.raises(ValueError, match="must not contain"):
            SampleDoc(id="a\\b", category=PK("a"), title="t")

    def test_id_exactly_1023_bytes_ok(self):
        ok_id = "x" * 1023
        doc = SampleDoc(id=ok_id, category=PK("a"), title="t")
        assert doc.id == ok_id


# ---------------------------------------------------------------------------
# Partition key helpers
# ---------------------------------------------------------------------------

class TestPartitionKey:
    def test_get_partition_key_field(self):
        assert SampleDoc.get_partition_key_field() == "category"

    def test_get_partition_key_value(self):
        doc = SampleDoc(category=PK("books"), title="t")
        assert SampleDoc.get_partition_key_value(doc) == "books"

    def test_pk_property(self):
        doc = SampleDoc(category=PK("books"), title="t")
        assert doc.pk == "books"


# ---------------------------------------------------------------------------
# ETag
# ---------------------------------------------------------------------------

class TestETag:
    def test_creation(self):
        etag = ETag("abc")
        assert etag.value == "abc"

    def test_str(self):
        assert str(ETag("v1")) == "v1"

    def test_repr(self):
        assert repr(ETag("v1")) == "ETag('v1')"

    def test_equality_same_type(self):
        assert ETag("a") == ETag("a")
        assert ETag("a") != ETag("b")

    def test_equality_with_str(self):
        assert ETag("a") == "a"

    def test_hash(self):
        assert hash(ETag("a")) == hash("a")
        assert {ETag("a"), ETag("a")} == {ETag("a")}


# ---------------------------------------------------------------------------
# PK wrapper
# ---------------------------------------------------------------------------

class TestPKWrapper:
    def test_creation(self):
        pk = PK("cat")
        assert pk.value == "cat"

    def test_str(self):
        assert str(PK("cat")) == "cat"

    def test_repr(self):
        assert repr(PK("cat")) == "PK('cat')"

    def test_equality_same_type(self):
        assert PK("a") == PK("a")
        assert PK("a") != PK("b")

    def test_equality_with_raw_value(self):
        assert PK("a") == "a"

    def test_hash(self):
        assert hash(PK(42)) == hash(42)
        assert {PK("a"), PK("a")} == {PK("a")}


# ---------------------------------------------------------------------------
# model_dump_cosmos / model_validate_cosmos
# ---------------------------------------------------------------------------

class TestCosmosSerialization:
    def test_model_dump_cosmos_produces_valid_dict(self):
        doc = SampleDoc(
            category=PK("books"),
            title="Hello",
            etag=ETag("e1"),
        )
        data = doc.model_dump_cosmos()

        # PK unwrapped
        assert data["category"] == "books"
        assert not isinstance(data["category"], PK)

        # ETag as string
        assert isinstance(data.get("etag"), str) or "etag" not in data

        # datetimes as ISO strings
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)

    def test_model_validate_cosmos_round_trip(self):
        doc = SampleDoc(category=PK("books"), title="Hello", etag=ETag("e1"))
        data = doc.model_dump_cosmos()
        restored = SampleDoc.model_validate_cosmos(data)

        assert isinstance(restored.category, PK)
        assert restored.category.value == "books"
        assert isinstance(restored.etag, ETag)
        assert restored.etag.value == "e1"
        assert isinstance(restored.created_at, datetime)
        assert restored.title == "Hello"


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

class TestStateManagement:
    def test_enable_disable(self):
        doc = SampleDoc(category=PK("a"), title="t")
        doc.enable_state_management()
        assert doc._state_management_enabled is True
        doc.disable_state_management()
        assert doc._state_management_enabled is False

    def test_is_changed(self):
        doc = SampleDoc(category=PK("a"), title="t")
        doc.enable_state_management()
        assert doc.is_changed is False
        doc.title = "changed"
        assert doc.is_changed is True

    def test_get_changes(self):
        doc = SampleDoc(category=PK("a"), title="t")
        doc.enable_state_management()
        doc.title = "new"
        changes = doc.get_changes()
        assert "title" in changes
        assert changes["title"] == "new"

    def test_rollback(self):
        doc = SampleDoc(category=PK("a"), title="t")
        doc.enable_state_management()
        doc.title = "changed"
        assert doc.is_changed is True
        doc.rollback()
        assert doc.title == "t"
        assert doc.is_changed is False

    def test_no_changes_when_disabled(self):
        doc = SampleDoc(category=PK("a"), title="t")
        assert doc.is_changed is False
        assert doc.get_changes() == {}


# ---------------------------------------------------------------------------
# @container decorator
# ---------------------------------------------------------------------------

class TestContainerDecorator:
    def test_sets_settings(self):
        settings = SampleDoc.get_container_settings()
        assert isinstance(settings, ContainerSettings)
        assert settings.name == "test_items"
        assert settings.partition_key_path == "/category"

    def test_vector_policy(self):
        settings = SampleDoc.get_container_settings()
        assert len(settings.vector_policy) == 1
        assert isinstance(settings.vector_policy[0], VectorPolicySpec)
        assert settings.vector_policy[0].path == "/embedding"
        assert settings.vector_policy[0].data_type == "float32"
        assert settings.vector_policy[0].dimensions == 4

    def test_vector_indexes(self):
        settings = SampleDoc.get_container_settings()
        assert len(settings.vector_indexes) == 1
        assert isinstance(settings.vector_indexes[0], VectorIndexSpec)
        assert settings.vector_indexes[0].path == "/embedding"
        assert settings.vector_indexes[0].type == "flat"

    def test_full_text_indexes(self):
        settings = SampleDoc.get_container_settings()
        assert len(settings.full_text_indexes) == 1
        assert isinstance(settings.full_text_indexes[0], FullTextIndexSpec)
        assert settings.full_text_indexes[0].paths == ["/title", "/content"]

    def test_missing_container_settings_not_configured(self):
        class Bare(Document):
            pass

        # Without @container, _container_settings is a Pydantic ModelPrivateAttr
        # sentinel, not a ContainerSettings instance.
        settings = Bare.get_container_settings()
        from cosmos_odm.types import ContainerSettings
        assert not isinstance(settings, ContainerSettings)


# ---------------------------------------------------------------------------
# @embeddings decorator
# ---------------------------------------------------------------------------

class TestEmbeddingsDecorator:
    def test_sets_embedding_config(self):
        @embeddings(field="content", dest="content_vector", dims=128)
        def embed_fn(text):
            return [0.0] * 128

        assert embed_fn._embedding_config == {
            "field": "content",
            "dest": "content_vector",
            "dims": 128,
        }
