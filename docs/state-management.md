# Smart State Management

State management enables efficient updates by tracking document changes and optimizing database operations to only send modified fields.

## State Management Features

The state management system automatically tracks document changes and provides

- **Change tracking** to monitor which fields have been modified
- **Rollback capabilities** to undo local changes
- **Optimized updates** that only send changed fields to reduce RU consumption
- **State inspection** to understand document modification status

## Enabling State Management

### Model-Level Configuration

Enable state management for all instances of a document model:

```python
from cosmos_odm import Document, container, PK

@container(
    database="myapp",
    name="documents",
    partition_key_paths=["/tenantId"]
)
class TrackedDocument(Document):
    id: str
    tenantId: PK[str]
    title: str
    content: str
    status: str = "draft"
    
    class Config:
        # Enable automatic state management for all instances
        state_management = True
```

### Instance-Level Configuration

Enable state management for individual document instances:

```python
# Create document and enable state tracking
doc = Document(
    id="doc-1", 
    tenantId=PK("tenant-1"), 
    title="Original Title",
    content="Original content"
)

# Enable state management for this instance
doc._enable_state_management()
```

## Change Tracking

### Detecting Changes

```python
# Create and modify document
doc = TrackedDocument(
    id="doc-1", 
    tenantId=PK("tenant-1"), 
    title="Original Title",
    content="Original content"
)

# Make some changes
doc.title = "Updated Title"
doc.content = "Updated content"

# Check if document has any changes
if doc.is_changed:
    print("Document has been modified")
    
    # Get dictionary of changed fields and their new values
    changes = doc.get_changes()
    print(f"Changed fields: {changes}")
    # Output: {'title': 'Updated Title', 'content': 'Updated content'}
```

### Change Details

The `get_changes()` method returns a dictionary containing only the fields that have been modified since the document was last saved or loaded:

```python
original_doc = TrackedDocument(
    id="doc-1",
    tenantId=PK("tenant-1"),
    title="Original Title",
    content="Original content",
    status="draft"
)

# Enable state tracking
original_doc._enable_state_management()

# Modify multiple fields
original_doc.title = "New Title"
original_doc.status = "published"
# Note: content field is unchanged

changes = original_doc.get_changes()
print(changes)
# Output: {'title': 'New Title', 'status': 'published'}
# Note: 'content' is not included since it wasn't changed
```

## Rollback Operations

### Rolling Back All Changes

Restore the document to its original state:

```python
# Make changes
doc.title = "Modified Title"
doc.content = "Modified content"

# Confirm changes exist
assert doc.is_changed
print(f"Changes: {doc.get_changes()}")

# Rollback all changes
doc.rollback()

# Verify rollback
assert not doc.is_changed
print(f"Title restored to: {doc.title}")  # Original title
print(f"Content restored to: {doc.content}")  # Original content
```

### Selective Field Rollback

```python
# For more granular control, you can manually restore specific fields
original_values = doc._get_original_values()  # Internal method
doc.title = original_values.get("title", doc.title)
```

## Optimized Database Operations

### Efficient Updates with save_changes()

When state management is enabled, you can use `save_changes()` to only update modified fields:

```python
# Load document from database
doc = await docs.get(pk="tenant-1", id="doc-1")

# Enable state tracking (if not already enabled on model)
doc._enable_state_management()

# Make selective changes
doc.title = "Updated Title"
doc.status = "published"
# Leave other fields unchanged

# Save only the changed fields (more efficient)
if doc.is_changed:
    updated_doc = await docs.save_changes(doc)
    print(f"Updated fields: {doc.get_changes()}")
    print(f"RU consumed: {updated_doc._ru_metrics.request_charge}")
```

This approach is more efficient than `save()` or `replace()` which send the entire document.

## State Lifecycle

### Document State Flow

```python
# 1. Create new document (no state tracking yet)
doc = TrackedDocument(id="doc-1", tenantId=PK("tenant-1"), title="Title")

# 2. Enable state management
doc._enable_state_management()
print(f"Initial state - Changed: {doc.is_changed}")  # False

# 3. Make changes
doc.title = "New Title"
print(f"After changes - Changed: {doc.is_changed}")  # True

# 4. Save to database
saved_doc = await docs.save_changes(doc)
print(f"After save - Changed: {saved_doc.is_changed}")  # False (state reset)

# 5. Make more changes
saved_doc.content = "New content"
print(f"After more changes - Changed: {saved_doc.is_changed}")  # True

# 6. Rollback changes
saved_doc.rollback()
print(f"After rollback - Changed: {saved_doc.is_changed}")  # False
```

## Advanced Usage Patterns

### Conditional Updates

Only update if specific fields have changed:

```python
# Check if critical fields have changed
critical_fields = {"title", "status", "priority"}
changed_fields = set(doc.get_changes().keys())

if critical_fields.intersection(changed_fields):
    print("Critical fields changed, updating document")
    await docs.save_changes(doc)
else:
    print("No critical changes, skipping update")
```

### Change Auditing

Track what fields are being modified for auditing purposes:

```python
def audit_changes(doc: TrackedDocument, user_id: str):
    if doc.is_changed:
        changes = doc.get_changes()
        audit_log = {
            "document_id": doc.id,
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "changes": changes
        }
        # Log to audit system
        logger.info(f"Document changes: {audit_log}")

# Usage
doc.title = "Updated by user"
audit_changes(doc, "user-123")
await docs.save_changes(doc)
```

### Batch State Management

Efficiently handle multiple documents with state tracking:

```python
async def batch_update_with_state_tracking():
    # Load multiple documents
    docs_to_update = await docs.find().where("status").equals("draft").to_list()
    
    # Enable state tracking for all
    for doc in docs_to_update:
        doc._enable_state_management()
    
    # Make bulk changes
    for doc in docs_to_update:
        doc.status = "published"
        doc.published_date = datetime.utcnow()
    
    # Save only documents that actually changed
    updated_docs = []
    for doc in docs_to_update:
        if doc.is_changed:
            updated_doc = await docs.save_changes(doc)
            updated_docs.append(updated_doc)
    
    return updated_docs
```

## Performance Benefits

### RU Consumption Optimization

State management can significantly reduce RU consumption:

```python
# Without state management - sends entire document
await docs.save(doc)  # ~10 RUs for large document

# With state management - sends only changed fields  
await docs.save_changes(doc)  # ~3 RUs for same document with few changes
```

### Network Efficiency

- **Reduced payload size**: Only modified fields are transmitted
- **Faster operations**: Less data to process and validate
- **Lower latency**: Smaller requests complete faster

## Best Practices

### When to Enable State Management

✅ **Good use cases:**
- Documents that are frequently updated with small changes
- Interactive applications with real-time editing
- Scenarios where RU optimization is critical
- When you need change auditing

❌ **Avoid when:**
- Documents are typically replaced entirely
- Memory usage is a primary concern
- Documents are rarely updated after creation

### Memory Considerations

State management stores original field values in memory:

```python
# For memory-sensitive applications, disable after use
doc.title = "Updated"
await docs.save_changes(doc)
doc._disable_state_management()  # Free up memory
```

### Integration with Other Features

State management works seamlessly with:
- Advanced CRUD operations
- Merge strategies
- Bulk operations
- Query builders

## Related Documentation

- [Advanced CRUD Operations](advanced-crud.md) - Advanced save and update patterns
- [Bulk Operations](bulk-operations.md) - Batch processing with state management
- [API Reference](api-reference.md) - Complete method signatures and parameters