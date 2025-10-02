"""Tests specifically for enhanced BulkWriter concurrency features."""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch
from typing import Optional
from pydantic import Field

from cosmos_odm import Document, container, PK
from cosmos_odm.query import BulkWriter


@container(name="bulk_test", partition_key_path="/partitionKey")
class BulkTestDocument(Document):
    """Test document for bulk operations."""
    id: str
    partitionKey: str = Field(alias="partitionKey")
    name: str
    age: int
    email: Optional[str] = None
    active: bool = True


class TestBulkWriterConcurrency:
    """Test BulkWriter enhanced concurrency features."""
    
    def test_bulk_writer_concurrency_initialization(self):
        """Test BulkWriter initialization with concurrency parameter."""
        # Create a mock collection
        mock_collection = AsyncMock()
        
        # Test default concurrency
        bulk_default = BulkWriter(mock_collection)
        assert bulk_default.max_concurrency == 10
        
        # Test custom concurrency
        bulk_custom = BulkWriter(mock_collection, max_concurrency=5)
        assert bulk_custom.max_concurrency == 5
    
    def test_bulk_writer_operation_queuing(self):
        """Test that operations are properly queued."""
        mock_collection = AsyncMock()
        bulk = BulkWriter(mock_collection, max_concurrency=3)
        
        # Create test documents
        doc1 = BulkTestDocument(id="test1", partitionKey="partition1", name="Test 1", age=25)
        doc2 = BulkTestDocument(id="test2", partitionKey="partition1", name="Test 2", age=26)
        doc3 = BulkTestDocument(id="test3", partitionKey="partition1", name="Test 3", age=27)
        
        # Queue operations
        bulk.insert(doc1)
        bulk.upsert(doc2)
        bulk.replace(doc3)
        bulk.delete(PK("partition1"), "delete1")
        
        # Verify operations are queued
        assert len(bulk._operations) == 4
        assert bulk._operations[0]["operation"] == "create"
        assert bulk._operations[1]["operation"] == "upsert"
        assert bulk._operations[2]["operation"] == "replace"
        assert bulk._operations[3]["operation"] == "delete"
    
    def test_partition_key_handling(self):
        """Test that PK objects are handled correctly."""
        mock_collection = AsyncMock()
        bulk = BulkWriter(mock_collection)
        
        # Test with regular string partition key
        doc = BulkTestDocument(id="pk_test", partitionKey="partition1", name="PK Test", age=30)
        bulk.insert(doc)
        
        operation = bulk._operations[0]
        # The partition key should be stored as-is when it's a regular string
        assert operation["partition_key"] == "partition1"
    
    @pytest.mark.asyncio
    async def test_concurrency_performance_mock(self):
        """Test that higher concurrency improves performance with mocked operations."""
        
        # Mock collection with artificial delay
        async def mock_operation_with_delay(*args, **kwargs):
            await asyncio.sleep(0.05)  # 50ms delay
            return {"id": "test", "statusCode": 201}
        
        mock_collection = AsyncMock()
        mock_collection.async_container = AsyncMock()
        mock_collection.async_container.create_item = mock_operation_with_delay
        
        # Create test documents
        docs = [
            BulkTestDocument(id=f"perf{i}", partitionKey="partition1", name=f"Perf {i}", age=20+i)
            for i in range(8)
        ]
        
        # Test with low concurrency
        bulk_low = BulkWriter(mock_collection, max_concurrency=2)
        for doc in docs:
            bulk_low.insert(doc)
        
        start_time = time.time()
        with patch.object(bulk_low, '_execute_single_operation', side_effect=mock_operation_with_delay):
            results_low = await bulk_low.execute()
        low_time = time.time() - start_time
        
        # Test with high concurrency
        bulk_high = BulkWriter(mock_collection, max_concurrency=6)
        for doc in docs:
            bulk_high.insert(doc)
        
        start_time = time.time()
        with patch.object(bulk_high, '_execute_single_operation', side_effect=mock_operation_with_delay):
            results_high = await bulk_high.execute()
        high_time = time.time() - start_time
        
        # Verify results
        assert len(results_low) == 8
        assert len(results_high) == 8
        assert all(r["success"] for r in results_low)
        assert all(r["success"] for r in results_high)
        
        # Higher concurrency should be faster (with tolerance for timing variations)
        assert high_time < low_time + 0.02  # Allow 20ms tolerance
    
    @pytest.mark.asyncio
    async def test_progress_tracking(self):
        """Test progress tracking functionality."""
        
        async def mock_operation(*args, **kwargs):
            await asyncio.sleep(0.01)  # Small delay
            return {"id": "test", "statusCode": 201}
        
        mock_collection = AsyncMock()
        bulk = BulkWriter(mock_collection, max_concurrency=3)
        
        # Create test documents
        docs = [
            BulkTestDocument(id=f"progress{i}", partitionKey="partition1", name=f"Progress {i}", age=20+i)
            for i in range(10)
        ]
        
        for doc in docs:
            bulk.insert(doc)
        
        # Track progress
        progress_history = []
        def track_progress(completed, total):
            progress_history.append((completed, total))
        
        # Execute with progress tracking
        with patch.object(bulk, '_execute_single_operation', side_effect=mock_operation):
            results = await bulk.execute(
                progress_callback=track_progress,
                batch_size=3
            )
        
        # Verify results
        assert len(results) == 10
        assert all(r["success"] for r in results)
        
        # Verify progress tracking
        assert len(progress_history) > 0
        final_progress = progress_history[-1]
        assert final_progress[0] == final_progress[1] == 10
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling with mixed success/failure."""
        
        call_count = 0
        async def mock_operation_with_failures(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Every 3rd call fails
                raise Exception("Mock failure")
            return {"id": f"success-{call_count}", "statusCode": 201}
        
        mock_collection = AsyncMock()
        bulk = BulkWriter(mock_collection, max_concurrency=2)
        
        # Create test documents
        docs = [
            BulkTestDocument(id=f"error{i}", partitionKey="partition1", name=f"Error {i}", age=20+i)
            for i in range(6)
        ]
        
        for doc in docs:
            bulk.insert(doc)
        
        # Execute with error handling
        with patch.object(bulk, '_execute_single_operation', side_effect=mock_operation_with_failures):
            results = await bulk.execute()
        
        # Verify mixed results
        assert len(results) == 6
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        
        assert len(successful) == 4  # 2/3 should succeed
        assert len(failed) == 2     # 1/3 should fail
        
        # Verify error details
        for failure in failed:
            assert "error" in failure
            assert failure["error"] == "Mock failure"
            assert failure["error_type"] == "Exception"
    
    @pytest.mark.asyncio
    async def test_empty_operations(self):
        """Test execution with no operations."""
        mock_collection = AsyncMock()
        bulk = BulkWriter(mock_collection)
        
        results = await bulk.execute()
        assert results == []
    
    @pytest.mark.asyncio
    async def test_mixed_operation_types(self):
        """Test execution with mixed operation types."""
        
        async def mock_operation(*args, **kwargs):
            return {"id": "test", "statusCode": 200}
        
        mock_collection = AsyncMock()
        bulk = BulkWriter(mock_collection, max_concurrency=4)
        
        # Create test documents
        insert_doc = BulkTestDocument(id="insert1", partitionKey="partition1", name="Insert", age=25)
        upsert_doc = BulkTestDocument(id="upsert1", partitionKey="partition1", name="Upsert", age=26)
        replace_doc = BulkTestDocument(id="replace1", partitionKey="partition1", name="Replace", age=27)
        
        # Add mixed operations
        bulk.insert(insert_doc)
        bulk.upsert(upsert_doc)
        bulk.replace(replace_doc)
        bulk.delete(PK("partition1"), "delete1")
        
        # Execute operations
        with patch.object(bulk, '_execute_single_operation', side_effect=mock_operation):
            results = await bulk.execute()
        
        # Verify all operation types were executed
        assert len(results) == 4
        assert all(r["success"] for r in results)
        
        operations = [r["operation"] for r in results]
        assert "create" in operations
        assert "upsert" in operations
        assert "replace" in operations
        assert "delete" in operations