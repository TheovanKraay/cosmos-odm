# Type-Safe Query Interface

The Cosmos ODM provides a fluent, type-safe query interface that generates optimized Azure Cosmos DB SQL while maintaining MongoDB-like syntax patterns.

## Overview

The query interface offers:

- **Fluent API** with method chaining for readable query construction
- **Type safety** with full IDE autocompletion and validation
- **SQL generation** that produces optimized Cosmos DB queries
- **Flexible execution** with various result formats (list, single, count, etc.)
- **Performance optimization** with built-in query analysis

## Basic Query Building

### Simple Queries

```python
# Find all published documents
results = await docs.find().where("status").equals("published").to_list()

# Find single document
doc = await docs.find().where("id").equals("doc-1").first()

# Count matching documents
count = await docs.find().where("category").equals("technology").count()
```

### Method Chaining

Build complex queries by chaining conditions:

```python
# Complex filtering with multiple conditions
results = await docs.find() \
    .where("tenantId").equals("tenant-1") \
    .where("created_date").greater_than("2024-01-01") \
    .where("status").in_values(["published", "draft"]) \
    .order_by("created_date", ascending=False) \
    .limit(10) \
    .to_list()
```

## Query Conditions

### String Operations

```python
# Exact match
await docs.find().where("title").equals("Introduction").to_list()

# Contains substring
await docs.find().where("content").contains("vector search").to_list()

# Starts with prefix
await docs.find().where("title").starts_with("Introduction").to_list()

# Ends with suffix
await docs.find().where("filename").ends_with(".pdf").to_list()
```

### Numeric Operations

```python
# Comparison operations
await docs.find().where("rating").greater_than(4.0).to_list()
await docs.find().where("price").less_than(100.0).to_list()
await docs.find().where("score").greater_than_or_equal(85).to_list()
await docs.find().where("age").less_than_or_equal(65).to_list()

# Range queries
await docs.find().where("price").between(10.0, 100.0).to_list()
```

### Array and List Operations

```python
# Value in array
await docs.find().where("tags").in_values(["ai", "ml", "search"]).to_list()

# Array contains value
await docs.find().where("categories").contains("technology").to_list()

# Array length
await docs.find().where("tags").array_length().greater_than(2).to_list()
```

### Boolean and Null Operations

```python
# Boolean values
await docs.find().where("is_published").equals(True).to_list()

# Null checks
await docs.find().where("deleted_date").is_null().to_list()
await docs.find().where("author").is_not_null().to_list()
```

## Sorting and Pagination

### Ordering Results

```python
# Single field sorting
await docs.find().order_by("created_date", ascending=False).to_list()

# Multiple field sorting
await docs.find() \
    .order_by("priority", ascending=False) \
    .order_by("created_date", ascending=True) \
    .to_list()
```

### Pagination

```python
# Limit results
await docs.find().limit(20).to_list()

# Skip and limit (pagination)
page_size = 10
page_number = 3
await docs.find() \
    .skip((page_number - 1) * page_size) \
    .limit(page_size) \
    .to_list()

# Offset-based pagination helper
async def paginate_results(page: int, page_size: int = 10):
    return await docs.find() \
        .where("status").equals("published") \
        .order_by("created_date", ascending=False) \
        .skip((page - 1) * page_size) \
        .limit(page_size) \
        .to_list()
```

## Advanced Query Patterns

### Complex Filtering

```python
# Multiple conditions on same field
await docs.find() \
    .where("created_date").greater_than("2024-01-01") \
    .where("created_date").less_than("2024-12-31") \
    .to_list()

# Combining different field conditions
await docs.find() \
    .where("category").equals("technology") \
    .where("published_date").greater_than("2024-01-01") \
    .where("author").in_values(["alice", "bob"]) \
    .where("rating").between(3.0, 5.0) \
    .to_list()
```

### Conditional Query Building

```python
def build_search_query(filters: dict):
    query = docs.find()
    
    # Add conditions based on provided filters
    if "category" in filters:
        query = query.where("category").equals(filters["category"])
    
    if "min_rating" in filters:
        query = query.where("rating").greater_than_or_equal(filters["min_rating"])
    
    if "tags" in filters:
        query = query.where("tags").in_values(filters["tags"])
    
    if "date_range" in filters:
        start, end = filters["date_range"]
        query = query.where("created_date").between(start, end)
    
    return query

# Usage
filters = {
    "category": "technology",
    "min_rating": 4.0,
    "tags": ["ai", "ml"],
    "date_range": ("2024-01-01", "2024-12-31")
}

results = await build_search_query(filters).to_list()
```

## Query Execution

### Result Formats

```python
# Get all results as list
all_docs = await docs.find().where("status").equals("published").to_list()

# Get first matching document
first_doc = await docs.find().where("featured").equals(True).first()

# Count matching documents without fetching them
count = await docs.find().where("category").equals("news").count()

# Check if any documents match
exists = await docs.find().where("urgent").equals(True).exists()
```

### Iterator Pattern

```python
# Process results one by one (memory efficient for large result sets)
async for doc in docs.find().where("status").equals("published"):
    print(f"Processing: {doc.title}")
    # Process document
```

### Batch Processing

```python
# Process in batches
query = docs.find().where("needs_processing").equals(True)
batch_size = 100

while True:
    batch = await query.limit(batch_size).to_list()
    if not batch:
        break
        
    # Process batch
    for doc in batch:
        await process_document(doc)
    
    # Update query to skip processed documents
    last_id = batch[-1].id
    query = query.where("id").greater_than(last_id)
```

## SQL Generation and Inspection

### Viewing Generated SQL

```python
# Build query
query = docs.find() \
    .where("status").equals("published") \
    .where("rating").greater_than(4.0) \
    .order_by("created_date", ascending=False) \
    .limit(10)

# Inspect generated SQL
sql = query.to_sql()
print(f"Generated SQL: {sql}")
# Output: SELECT * FROM c WHERE c.status = "published" AND c.rating > 4.0 ORDER BY c.created_date DESC LIMIT 10
```

### Query Analysis

```python
# Get query execution plan (useful for optimization)
query_info = query.get_query_info()
print(f"Estimated RU cost: {query_info.get('estimated_ru', 'Unknown')}")
print(f"Uses index: {query_info.get('uses_index', 'Unknown')}")
```

## Performance Optimization

### Index-Friendly Queries

```python
# Good: Uses partition key for efficient lookup
await docs.find() \
    .where("tenantId").equals("tenant-1") \
    .where("status").equals("published") \
    .to_list()

# Good: Range query on indexed field
await docs.find() \
    .where("created_date").between("2024-01-01", "2024-12-31") \
    .to_list()
```

### Query Hints and Optimization

```python
# Use query hints for optimization
query = docs.find() \
    .where("category").equals("technology") \
    .hint("use_index", "category_index") \
    .limit(100)

# Enable cross-partition queries when needed
query = docs.find() \
    .where("global_status").equals("active") \
    .enable_cross_partition() \
    .to_list()
```

## Real-World Examples

### Content Management System

```python
async def get_articles(filters):
    """Get articles with various filtering options"""
    query = docs.find()
    
    # Apply filters
    if filters.get("category"):
        query = query.where("category").equals(filters["category"])
    
    if filters.get("author"):
        query = query.where("author").equals(filters["author"])
    
    if filters.get("published_after"):
        query = query.where("published_date").greater_than(filters["published_after"])
    
    if filters.get("tags"):
        query = query.where("tags").in_values(filters["tags"])
    
    if filters.get("min_rating"):
        query = query.where("rating").greater_than_or_equal(filters["min_rating"])
    
    # Apply sorting and pagination
    query = query.order_by("published_date", ascending=False)
    
    if filters.get("page") and filters.get("page_size"):
        page = filters["page"]
        page_size = filters["page_size"]
        query = query.skip((page - 1) * page_size).limit(page_size)
    
    return await query.to_list()
```

### Analytics and Reporting

```python
async def generate_content_report():
    """Generate analytics report using query interface"""
    
    # Count by category
    categories = ["technology", "business", "lifestyle"]
    category_counts = {}
    
    for category in categories:
        count = await docs.find().where("category").equals(category).count()
        category_counts[category] = count
    
    # Recent popular content
    popular_recent = await docs.find() \
        .where("created_date").greater_than("2024-01-01") \
        .where("rating").greater_than_or_equal(4.0) \
        .order_by("views", ascending=False) \
        .limit(10) \
        .to_list()
    
    # Authors with most content
    top_authors = await docs.find() \
        .where("status").equals("published") \
        .group_by("author") \
        .order_by("count", ascending=False) \
        .limit(5) \
        .to_list()
    
    return {
        "category_counts": category_counts,
        "popular_recent": popular_recent,
        "top_authors": top_authors
    }
```

### Search and Discovery

```python
async def advanced_search(search_params):
    """Advanced search with multiple criteria"""
    query = docs.find()
    
    # Text search
    if search_params.get("query"):
        query = query.where("title").contains(search_params["query"]) \
                     .or_where("content").contains(search_params["query"])
    
    # Date range
    if search_params.get("date_from") and search_params.get("date_to"):
        query = query.where("created_date").between(
            search_params["date_from"], 
            search_params["date_to"]
        )
    
    # Multiple tag filtering
    if search_params.get("required_tags"):
        for tag in search_params["required_tags"]:
            query = query.where("tags").contains(tag)
    
    # Exclude certain content
    if search_params.get("exclude_categories"):
        query = query.where("category").not_in(search_params["exclude_categories"])
    
    # Sort by relevance or date
    sort_by = search_params.get("sort_by", "relevance")
    if sort_by == "date":
        query = query.order_by("created_date", ascending=False)
    elif sort_by == "rating":
        query = query.order_by("rating", ascending=False)
    
    return await query.to_list()
```

## Best Practices

### Query Construction

✅ **Good practices:**
- Use partition key filters when possible
- Leverage indexed fields for filtering
- Combine filters efficiently
- Use appropriate result methods (`first()`, `count()`, etc.)

❌ **Avoid:**
- Cross-partition queries unless necessary
- Filtering on non-indexed fields
- Overly complex nested conditions
- Fetching more data than needed

### Performance Tips

1. **Use partition key filtering**: Always include partition key when possible
2. **Index awareness**: Filter on indexed fields for better performance
3. **Limit results**: Use `limit()` to control result size
4. **Batch processing**: Process large result sets in batches
5. **SQL inspection**: Use `to_sql()` to verify query optimization

## Related Documentation

- [Advanced CRUD Operations](advanced-crud.md) - Advanced document operations
- [Bulk Operations](bulk-operations.md) - Batch processing with queries
- [Search Features](search.md) - Vector and full-text search integration
- [API Reference](api-reference.md) - Complete query method signatures