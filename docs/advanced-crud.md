# Advanced CRUD Operations

The Cosmos ODM provides advanced CRUD operations inspired by MongoDB patterns but optimized for Azure Cosmos DB's capabilities.

## Smart Save Operation

Advanced CRUD operations provide intelligent document management with automatic conflict resolution, optimized database operations, and seamless state management integration.

- **Smart save operations** that handle both insert and replace scenarios
- **Conflict resolution** with customizable merge strategies  
- **Optimistic concurrency** control with ETag support
- **Sync operations** to fetch the latest version from the server
- **State-aware saves** that only update modified fields

## Save Operations

### Basic Save

The `save()` method intelligently handles both document creation and updates:

```python
# Create or update with save() - handles both insert and replace
doc = Document(
    id="doc-1",
    tenantId=PK("tenant-1"),
    title="My Document",
    content="Some content"
)

# Smart save - creates if new, replaces if exists
saved_doc = await docs.save(doc)
print(f"Saved with RU: {saved_doc._ru_metrics.request_charge}")
```

### Save with Conflict Resolution

```python
from cosmos_odm.model import MergeStrategy

# Save with different merge strategies
saved_doc = await docs.save(doc, merge_strategy=MergeStrategy.MERGE_FIELDS)
```

### Save Changes Only

For documents with state management enabled, you can save only the modified fields:

```python
# Only saves if document has local changes
if doc.is_changed:
    saved_doc = await docs.save_changes(doc)
    print(f"Updated fields: {doc.get_changes()}")
```

## Replace Operations

### Advanced Replace Operation

Replace operations update the entire document while supporting conflict resolution:

```python
# Replace entire document
replaced_doc = await docs.replace_document(doc)

# Replace with conflict resolution and optimistic concurrency
replaced_doc = await docs.replace_document(
    doc, 
    merge_strategy=MergeStrategy.PREFER_NEWER,
    if_match=doc.etag.value  # Optimistic concurrency control
)
```

## Sync Operations

### Fetch Latest Version

Sync operations retrieve the latest version of a document from the server:

```python
# Sync changes from server (fetch latest version)
synced_doc = await docs.sync_document(doc)

# The synced document contains the latest server state
print(f"Server version: {synced_doc.etag.value}")
```

## Merge Strategies

The ODM supports several merge strategies for handling conflicts:

### MergeStrategy.REPLACE_ENTIRE (Default)
```python
# Replaces the entire document with the new version
await docs.save(doc, merge_strategy=MergeStrategy.REPLACE_ENTIRE)
```

### MergeStrategy.MERGE_FIELDS
```python
# Merges non-null fields from the new document into the existing one
await docs.save(doc, merge_strategy=MergeStrategy.MERGE_FIELDS)
```

### MergeStrategy.PREFER_NEWER
```python
# Uses the newer document based on timestamp comparison
await docs.save(doc, merge_strategy=MergeStrategy.PREFER_NEWER)
```

### MergeStrategy.PREFER_EXISTING
```python
# Keeps the existing document, ignores new values
await docs.save(doc, merge_strategy=MergeStrategy.PREFER_EXISTING)
```

## Practical Examples

### Document Lifecycle Management

```python
async def document_lifecycle_example():
    # Create new document
    doc = Document(
        id="article-1",
        tenantId=PK("blog"),
        title="Getting Started with Cosmos ODM",
        content="This article covers...",
        status="draft"
    )
    
    # Initial save (creates document)
    saved_doc = await docs.save(doc)
    
    # Update and save changes
    saved_doc.status = "published"
    saved_doc.published_date = datetime.utcnow()
    
    # Save with optimistic concurrency
    updated_doc = await docs.save(saved_doc, if_match=saved_doc.etag.value)
    
    # Sync to get latest version
    latest_doc = await docs.sync_document(updated_doc)
    
    return latest_doc
```

### Conflict Resolution Example

```python
async def handle_conflicts():
    # Two users editing the same document
    doc1 = await docs.get(pk="tenant-1", id="shared-doc")
    doc2 = await docs.get(pk="tenant-1", id="shared-doc")
    
    # User 1 updates title
    doc1.title = "Updated by User 1"
    await docs.save(doc1)
    
    # User 2 updates content (potential conflict)
    doc2.content = "Updated by User 2"
    
    # Use merge strategy to combine changes
    merged_doc = await docs.save(doc2, merge_strategy=MergeStrategy.MERGE_FIELDS)
    
    # Result: document has both title from User 1 and content from User 2
    return merged_doc
```

## Best Practices

### When to Use Each Operation

- **`save()`**: When you want automatic insert/update behavior
- **`replace_document()`**: When you need to replace the entire document
- **`save_changes()`**: When using state management and only want to update modified fields
- **`sync_document()`**: When you need to fetch the latest server version

### Performance Considerations

- Use `save_changes()` with state management to minimize RU consumption
- Enable optimistic concurrency with ETag for conflict detection
- Choose appropriate merge strategies based on your conflict resolution needs
- Consider using bulk operations for multiple documents

### Error Handling

```python
from azure.cosmos.exceptions import CosmosHttpResponseError

try:
    # Save with optimistic concurrency
    saved_doc = await docs.save(doc, if_match=doc.etag.value)
except CosmosHttpResponseError as e:
    if e.status_code == 412:  # Precondition failed
        # Handle conflict - sync and retry
        synced_doc = await docs.sync_document(doc)
        # Apply your changes to synced version and retry
        saved_doc = await docs.save(synced_doc)
    else:
        raise
```

## Related Documentation

- [Document State Management](state-management.md) - Change tracking and optimization
- [API Reference](api-reference.md) - Complete method signatures and parameters
- [Query Interface](query-interface.md) - Advanced querying capabilities