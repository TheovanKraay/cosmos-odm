"""Unit tests for SQL generation and core functionality."""

import pytest
from typing import List, Dict, Any
from datetime import datetime

from cosmos_odm.search_native import SearchQueryBuilder, IndexManager
from cosmos_odm.filters import FilterBuilder
from cosmos_odm.model import Document, container, PK, ETag
from cosmos_odm.types import VectorPolicySpec, VectorIndexSpec, FullTextIndexSpec, ContainerSettings


class TestSearchQueryBuilder:
    """Test SQL generation for search operations."""
    
    def setup_method(self):
        self.builder = SearchQueryBuilder()
        self.filter_builder = FilterBuilder()
    
    def test_vector_search_simple(self):
        """Test basic vector search query generation."""
        vector = [0.1, 0.2, 0.3]
        
        sql, params = self.builder.build_vector_search(
            vector=vector,
            vector_path="/content_vector",
            k=5
        )
        
        expected_sql = """SELECT TOP @k c
FROM c
ORDER BY RANK VectorDistance(c/content_vector, @vector)"""
        
        assert sql == expected_sql
        assert len(params) == 2
        assert params[0] == {"name": "@k", "value": 5}
        assert params[1] == {"name": "@vector", "value": vector}
    
    def test_vector_search_with_filter(self):
        """Test vector search with filter conditions."""
        vector = [0.1, 0.2, 0.3]
        filter_dict = {"status": "published", "category": "tech"}
        
        sql, params = self.builder.build_vector_search(
            vector=vector,
            vector_path="/content_vector",
            k=10,
            filter=filter_dict,
            filter_builder=self.filter_builder
        )
        
        assert "WHERE" in sql
        assert "c.status = @param0" in sql
        assert "c.category = @param1" in sql
        assert "ORDER BY RANK VectorDistance" in sql
        assert len(params) >= 4  # k, vector, plus filter params
    
    def test_full_text_search_single_field(self):
        """Test full-text search on a single field."""
        sql, params = self.builder.build_full_text_search(
            text="machine learning",
            fields=["/content"],
            k=10
        )
        
        expected_sql = """SELECT TOP @k c
FROM c
ORDER BY RANK FullTextScore(c/content, @text)"""
        
        assert sql == expected_sql
        assert len(params) == 2
        assert params[0] == {"name": "@k", "value": 10}
        assert params[1] == {"name": "@text", "value": "machine learning"}
    
    def test_full_text_search_multiple_fields(self):
        """Test full-text search on multiple fields."""
        sql, params = self.builder.build_full_text_search(
            text="python programming",
            fields=["/title", "/content"],
            k=5
        )
        
        assert "FullTextScore(c/title, @text)" in sql
        assert "FullTextScore(c/content, @text)" in sql
        assert "ORDER BY RANK" in sql
        assert len(params) == 2
    
    def test_hybrid_search_basic(self):
        """Test hybrid search with RRF."""
        vector = [0.1, 0.2, 0.3, 0.4]
        
        sql, params = self.builder.build_hybrid_search(
            text="artificial intelligence",
            vector=vector,
            fields=["/content"],
            vector_path="/content_vector",
            k=10
        )
        
        assert "RRF(" in sql
        assert "FullTextScore(" in sql
        assert "VectorDistance(" in sql
        assert "ORDER BY RANK" in sql
        assert len(params) == 3  # k, text, vector
    
    def test_hybrid_search_with_weights(self):
        """Test hybrid search with RRF weights."""
        vector = [0.1, 0.2, 0.3]
        weights = [2, 1]  # Favor text over vector
        
        sql, params = self.builder.build_hybrid_search(
            text="deep learning",
            vector=vector,
            fields=["/content"],
            vector_path="/content_vector",
            k=5,
            weights=weights
        )
        
        assert "RRF(" in sql
        assert "@weights" in sql
        assert len(params) == 4  # k, text, vector, weights


class TestFilterBuilder:
    """Test filter to SQL conversion."""
    
    def setup_method(self):
        self.builder = FilterBuilder()
    
    def test_simple_equality_filter(self):
        """Test simple field equality."""
        filter_dict = {"status": "active"}
        
        sql, params = self.builder.build_filter(filter_dict)
        
        assert sql == "c.status = @param0"
        assert len(params) == 1
        assert params[0] == {"name": "@param0", "value": "active"}
    
    def test_multiple_equality_filters(self):
        """Test multiple field equality with AND."""
        filter_dict = {"status": "active", "category": "tech"}
        
        sql, params = self.builder.build_filter(filter_dict)
        
        assert "c.status = @param0" in sql
        assert "c.category = @param1" in sql
        assert " AND " in sql
        assert len(params) == 2
    
    def test_comparison_operators(self):
        """Test comparison operators."""
        filter_dict = {"age": {"$gte": 18, "$lt": 65}}
        
        sql, params = self.builder.build_filter(filter_dict)
        
        assert "c.age >= @param0" in sql
        assert "c.age < @param1" in sql
        assert " AND " in sql
        assert len(params) == 2
        assert params[0]["value"] == 18
        assert params[1]["value"] == 65
    
    def test_in_operator(self):
        """Test $in operator."""
        filter_dict = {"category": {"$in": ["tech", "science", "ai"]}}
        
        sql, params = self.builder.build_filter(filter_dict)
        
        assert "c.category IN (" in sql
        assert "@param0, @param1, @param2" in sql
        assert len(params) == 3
        assert [p["value"] for p in params] == ["tech", "science", "ai"]
    
    def test_exists_operator(self):
        """Test $exists operator."""
        filter_dict = {"optional_field": {"$exists": True}}
        
        sql, params = self.builder.build_filter(filter_dict)
        
        assert sql == "IS_DEFINED(c.optional_field)"
        assert len(params) == 0
    
    def test_string_operations(self):
        """Test string contains/startswith/endswith."""
        filter_dict = {"title": {"$contains": "python"}}
        
        sql, params = self.builder.build_filter(filter_dict)
        
        assert sql == "CONTAINS(c.title, @param0)"
        assert len(params) == 1
        assert params[0]["value"] == "python"


@container(
    name="test_docs",
    partition_key_path="/tenantId",
    vector_policy=[{"path": "/content_vector", "data_type": "float32", "dimensions": 4}],
    vector_indexes=[{"path": "/content_vector", "type": "flat"}],
    full_text_indexes=[{"paths": ["/title", "/content"]}]
)
class TestDoc(Document):
    """Test document for unit tests."""
    
    tenantId: PK[str]
    title: str
    content: str
    content_vector: List[float] = []
    status: str = "draft"


class TestDocumentModel:
    """Test Document base class functionality."""
    
    def test_document_creation(self):
        """Test basic document creation."""
        doc = TestDoc(
            id="test-1",
            tenantId=PK("tenant-1"),
            title="Test Document",
            content="This is a test document."
        )
        
        assert doc.id == "test-1"
        assert doc.tenantId.value == "tenant-1"
        assert doc.pk == "tenant-1"  # Partition key access
        assert doc.schema_version == 1
        assert doc.created_at is not None
        assert doc.updated_at is not None
    
    def test_container_settings(self):
        """Test container settings retrieval."""
        settings = TestDoc.get_container_settings()
        
        assert settings.name == "test_docs"
        assert settings.partition_key_path == "/tenantId"
        assert len(settings.vector_policy) == 1
        assert settings.vector_policy[0].path == "/content_vector"
        assert len(settings.vector_indexes) == 1
        assert len(settings.full_text_indexes) == 1
    
    def test_partition_key_extraction(self):
        """Test partition key value extraction."""
        doc = TestDoc(
            id="test-1",
            tenantId=PK("tenant-1"),
            title="Test",
            content="Content"
        )
        
        pk_field = TestDoc.get_partition_key_field()
        pk_value = TestDoc.get_partition_key_value(doc)
        
        assert pk_field == "tenantId"
        assert pk_value == "tenant-1"
    
    def test_cosmos_serialization(self):
        """Test serialization for Cosmos DB storage."""
        now = datetime.utcnow()
        doc = TestDoc(
            id="test-1",
            tenantId=PK("tenant-1"),
            title="Test Document",
            content="Content",
            etag=ETag("test-etag"),
            created_at=now,
            updated_at=now
        )
        
        data = doc.model_dump_cosmos()
        
        assert data["id"] == "test-1"
        assert data["tenantId"] == "tenant-1"  # PK unwrapped
        assert data["etag"] == "test-etag"  # ETag as string
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_cosmos_deserialization(self):
        """Test deserialization from Cosmos DB data."""
        now = datetime.utcnow().isoformat()
        data = {
            "id": "test-1",
            "tenantId": "tenant-1",
            "title": "Test Document",
            "content": "Content",
            "etag": "test-etag",
            "created_at": now,
            "updated_at": now,
            "schema_version": 1
        }
        
        doc = TestDoc.model_validate_cosmos(data)
        
        assert doc.id == "test-1"
        assert doc.tenantId.value == "tenant-1"
        assert isinstance(doc.etag, ETag)
        assert doc.etag.value == "test-etag"
        assert isinstance(doc.created_at, datetime)
        assert isinstance(doc.updated_at, datetime)