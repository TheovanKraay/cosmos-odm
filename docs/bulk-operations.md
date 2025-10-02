# Bulk Operations

Bulk operations enable efficient processing of multiple documents through batch operations, reducing round trips and optimizing Request Unit (RU) consumption.

## Overview

The Cosmos ODM provides comprehensive bulk operation capabilities:

- **BulkWriter**: Flexible batch processing with automatic batching
- **Collection bulk methods**: Convenient methods for common bulk operations
- **Efficient batching**: Automatic optimization of batch sizes
- **Error handling**: Robust error management for partial failures
- **RU optimization**: Minimized Request Unit consumption through batching

## BulkWriter Class

### Basic Usage

The `BulkWriter` provides a flexible interface for batching multiple operations:

```python
from cosmos_odm.query import BulkWriter

# Create bulk writer for efficient batch operations
bulk = BulkWriter(docs)

# Add multiple operations
documents_to_create = [
    Document(id=f"doc-{i}", tenantId=PK("tenant-1"), title=f"Document {i}")
    for i in range(100)
]

# Queue operations
for doc in documents_to_create:
    bulk.insert(doc)

# Execute all operations in batches
results = await bulk.execute()
print(f"Processed {len(results)} documents")
```

### Mixed Operations

Combine different operation types in a single bulk execution:

```python
bulk = BulkWriter(docs)

# Mix different operations
bulk.insert(new_doc1)
bulk.insert(new_doc2)
bulk.update(existing_doc1)
bulk.update(existing_doc2)
bulk.delete(doc_to_delete)

# Execute all operations together
results = await bulk.execute()
```

### Batch Size Configuration

Control batch sizes for optimal performance:

```python
# Create bulk writer with custom batch size
bulk = BulkWriter(docs, batch_size=25)

for doc in large_document_list:
    bulk.insert(doc)

# Execute with controlled batch sizes
results = await bulk.execute()
```

### Error Handling

Handle partial failures gracefully:

```python
bulk = BulkWriter(docs, batch_size=50)

for doc in documents:
    bulk.insert(doc)

try:
    results = await bulk.execute()
    print(f"Successfully processed {len(results)} documents")
except BulkOperationError as e:
    print(f"Bulk operation failed: {e}")
    
    # Access partial results
    if hasattr(e, 'partial_results'):
        print(f"Partial results: {len(e.partial_results)} succeeded")
        
    # Access failed operations
    if hasattr(e, 'failed_operations'):
        print(f"Failed operations: {len(e.failed_operations)}")
```

## Collection Bulk Methods

### Bulk Insert

Insert multiple documents efficiently:

```python
# Create multiple documents
documents = [
    Document(id=f"article-{i}", tenantId=PK("blog"), title=f"Article {i}")
    for i in range(50)
]

# Bulk insert with default batch size
created_docs = await docs.insert_many(documents)
print(f"Created {len(created_docs)} documents")

# Bulk insert with custom batch size
created_docs = await docs.insert_many(documents, batch_size=10)
```

### Bulk Delete

Delete multiple documents based on query conditions:

```python
# Delete all draft documents
deleted_count = await docs.delete_many(
    docs.find().where("status").equals("draft")
)
print(f"Deleted {deleted_count} documents")

# Delete documents by specific IDs
ids_to_delete = ["doc-1", "doc-2", "doc-3"]
deleted_count = await docs.delete_many(
    docs.find().where("id").in_values(ids_to_delete)
)
```

### Bulk Update

Update multiple documents with the same changes:

```python
# Update all published articles
update_fields = {"status": "archived", "archived_date": datetime.utcnow()}
updated_count = await docs.update_many(
    docs.find().where("status").equals("published"),
    update_fields
)
print(f"Updated {updated_count} documents")
```

## Advanced Bulk Patterns

### Conditional Bulk Operations

Perform bulk operations based on complex conditions:

```python
async def archive_old_content():
    # Find documents older than 1 year
    cutoff_date = datetime.utcnow() - timedelta(days=365)
    
    old_docs = await docs.find() \
        .where("created_date").less_than(cutoff_date.isoformat()) \
        .where("status").equals("published") \
        .to_list()
    
    if old_docs:
        # Use bulk writer for mixed operations
        bulk = BulkWriter(docs)
        
        for doc in old_docs:
            doc.status = "archived"
            doc.archived_date = datetime.utcnow()
            bulk.update(doc)
        
        results = await bulk.execute()
        return len(results)
    
    return 0
```

### Bulk Operations with State Management

Combine bulk operations with document state management:

```python
async def bulk_update_with_state_tracking():
    # Load documents with state management
    documents = await docs.find().where("needs_update").equals(True).to_list()
    
    # Enable state tracking for efficient updates
    for doc in documents:
        doc._enable_state_management()
    
    # Make changes
    bulk = BulkWriter(docs)
    for doc in documents:
        doc.last_updated = datetime.utcnow()
        doc.needs_update = False
        
        # Only add to bulk if document actually changed
        if doc.is_changed:
            bulk.update(doc)
    
    # Execute bulk update
    if bulk.has_operations():
        results = await bulk.execute()
        return len(results)
    
    return 0
```

### Parallel Bulk Processing

Process large datasets efficiently with parallel batching:

```python
import asyncio
from typing import List, Callable

async def parallel_bulk_process(
    documents: List[Document], 
    operation: Callable,
    max_workers: int = 5,
    batch_size: int = 100
):
    """Process documents in parallel bulk operations"""
    
    # Split documents into chunks for parallel processing
    chunks = [
        documents[i:i + batch_size] 
        for i in range(0, len(documents), batch_size)
    ]
    
    async def process_chunk(chunk):
        bulk = BulkWriter(docs, batch_size=batch_size)
        
        for doc in chunk:
            operation(bulk, doc)  # Apply operation to bulk writer
        
        return await bulk.execute()
    
    # Process chunks in parallel with limited concurrency
    semaphore = asyncio.Semaphore(max_workers)
    
    async def process_with_semaphore(chunk):
        async with semaphore:
            return await process_chunk(chunk)
    
    # Execute all chunks
    tasks = [process_with_semaphore(chunk) for chunk in chunks]
    results = await asyncio.gather(*tasks)
    
    # Flatten results
    all_results = []
    for chunk_results in results:
        all_results.extend(chunk_results)
    
    return all_results

# Usage
documents = await docs.find().where("status").equals("pending").to_list()

def mark_as_processed(bulk: BulkWriter, doc: Document):
    doc.status = "processed"
    doc.processed_date = datetime.utcnow()
    bulk.update(doc)

processed_docs = await parallel_bulk_process(
    documents, 
    mark_as_processed,
    max_workers=3,
    batch_size=50
)
```

## Performance Optimization

### Batch Size Tuning

Optimize batch sizes based on document size and complexity:

```python
# For small documents
bulk_small = BulkWriter(docs, batch_size=100)

# For large documents
bulk_large = BulkWriter(docs, batch_size=25)

# For documents with complex operations
bulk_complex = BulkWriter(docs, batch_size=10)
```

### RU Consumption Monitoring

Monitor Request Unit consumption during bulk operations:

```python
async def monitored_bulk_insert(documents):
    bulk = BulkWriter(docs, batch_size=50)
    
    for doc in documents:
        bulk.insert(doc)
    
    # Track RU consumption
    start_time = time.time()
    results = await bulk.execute()
    end_time = time.time()
    
    # Calculate metrics
    total_ru = sum(result._ru_metrics.request_charge for result in results)
    duration = end_time - start_time
    
    print(f"Bulk operation metrics:")
    print(f"  Documents processed: {len(results)}")
    print(f"  Total RU consumed: {total_ru}")
    print(f"  Duration: {duration:.2f} seconds")
    print(f"  RU per document: {total_ru / len(results):.2f}")
    print(f"  Documents per second: {len(results) / duration:.2f}")
    
    return results
```

### Memory-Efficient Bulk Processing

Process large datasets without loading everything into memory:

```python
async def memory_efficient_bulk_update(query_filter):
    """Process large result sets in memory-efficient batches"""
    
    batch_size = 100
    processed_count = 0
    
    # Process in pages to avoid memory issues
    while True:
        # Get next batch
        batch = await docs.find() \
            .where(query_filter) \
            .skip(processed_count) \
            .limit(batch_size) \
            .to_list()
        
        if not batch:
            break  # No more documents
        
        # Process batch
        bulk = BulkWriter(docs, batch_size=batch_size)
        
        for doc in batch:
            doc.last_processed = datetime.utcnow()
            bulk.update(doc)
        
        # Execute batch
        results = await bulk.execute()
        processed_count += len(results)
        
        print(f"Processed {processed_count} documents so far...")
    
    return processed_count
```

## Real-World Examples

### Data Migration

```python
async def migrate_document_format():
    """Migrate documents to new format using bulk operations"""
    
    # Find documents that need migration
    old_format_docs = await docs.find() \
        .where("format_version").less_than(2) \
        .to_list()
    
    if not old_format_docs:
        return 0
    
    bulk = BulkWriter(docs, batch_size=25)
    
    for doc in old_format_docs:
        # Transform to new format
        if hasattr(doc, 'old_field'):
            doc.new_field = transform_old_field(doc.old_field)
            delattr(doc, 'old_field')
        
        doc.format_version = 2
        doc.migration_date = datetime.utcnow()
        
        bulk.update(doc)
    
    results = await bulk.execute()
    return len(results)
```

### Content Publishing Workflow

```python
async def publish_scheduled_content():
    """Publish content that's scheduled for the current time"""
    
    now = datetime.utcnow()
    
    # Find content scheduled for publishing
    scheduled_docs = await docs.find() \
        .where("status").equals("scheduled") \
        .where("publish_date").less_than_or_equal(now.isoformat()) \
        .to_list()
    
    if not scheduled_docs:
        return []
    
    bulk = BulkWriter(docs)
    
    for doc in scheduled_docs:
        doc.status = "published"
        doc.published_date = now
        doc.publish_date = None  # Clear schedule
        
        bulk.update(doc)
    
    published_docs = await bulk.execute()
    
    # Log publication
    for doc in published_docs:
        logger.info(f"Published document: {doc.id}")
    
    return published_docs
```

### Cleanup Operations

```python
async def cleanup_expired_documents():
    """Clean up documents that have exceeded their TTL"""
    
    # Find expired documents
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    
    expired_docs = await docs.find() \
        .where("expires_date").less_than(cutoff_date.isoformat()) \
        .where("status").in_values(["expired", "deleted"]) \
        .to_list()
    
    if not expired_docs:
        return 0
    
    # Delete in batches
    deleted_count = await docs.delete_many(
        docs.find().where("id").in_values([doc.id for doc in expired_docs])
    )
    
    logger.info(f"Cleaned up {deleted_count} expired documents")
    return deleted_count
```

## Best Practices

### When to Use Bulk Operations

✅ **Good use cases:**
- Processing large numbers of documents (> 10)
- Data migration and transformation
- Scheduled batch jobs
- Content publishing workflows
- Cleanup operations

❌ **Avoid bulk operations for:**
- Single document operations
- Real-time user interactions
- Documents requiring individual validation
- Operations where partial failures are unacceptable

### Error Handling Strategies

1. **Retry failed operations**: Implement retry logic for transient failures
2. **Partial success handling**: Process successful operations even if some fail
3. **Logging and monitoring**: Track bulk operation metrics and failures
4. **Graceful degradation**: Fall back to individual operations if bulk fails

### Performance Guidelines

1. **Batch size optimization**: Test different batch sizes for your use case
2. **Parallel processing**: Use parallel bulk operations for large datasets
3. **Memory management**: Process large datasets in chunks
4. **RU monitoring**: Track Request Unit consumption to optimize costs
5. **Index awareness**: Ensure bulk operations use appropriate indexes

## Related Documentation

- [Advanced CRUD Operations](advanced-crud.md) - Individual document operations
- [Query Interface](query-interface.md) - Building queries for bulk operations
- [State Management](state-management.md) - Efficient updates with change tracking
- [API Reference](api-reference.md) - Complete bulk operation method signatures