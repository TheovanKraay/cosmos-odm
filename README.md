# Cosmos ODM

A production-grade, async-first **Azure Cosmos DB Core (SQL) ODM** for Python with native **vector search**, **full-text search**, and **hybrid search** capabilities built directly into Azure Cosmos DB for NoSQL.

> **⚠️ Experimental Package**: This package is currently experimental and has not yet been published to PyPI. See [Installation](#installation) section for local testing instructions.

## Features

### 🚀 **Core ODM Capabilities**
- **Async-first** with optional sync facade
- **Pydantic v2** models with full validation
- **Key-centric design**: partition key + id are first-class citizens
- **Point reads preferred** for optimal performance
- **ETag/optimistic concurrency** control
- **Request Unit (RU) telemetry** on every operation

### 🔍 **Native Search (No External Dependencies)**
- **Vector search** using Cosmos DB's `VectorDistance()` function
- **Full-text search** using Cosmos DB's `FullTextScore()` (BM25)
- **Hybrid search** using Cosmos DB's `RRF()` (Reciprocal Rank Fusion)
- **Cosmos-native indexing**: vector policies, vector indexes, full-text indexes

### 🛠 **Cosmos-Specific Features**
- **Transactional batches** (partition-scoped)
- **Patch operations** with conditional updates
- **Change Feed** with continuation tokens
- **Per-call consistency levels**
- **Container provisioning** with TTL, indexing, unique keys

## Installation

> **🧪 Experimental Installation**: This package is not yet available on PyPI. To test the package locally, you'll need to install it directly from the source code.

### Prerequisites
- Python 3.11 or higher
- Git (for cloning the repository)

### Local Installation for Testing

1. **Clone the repository**:
   ```bash
   git clone https://github.com/TheovanKraay/cosmos-odm.git
   cd cosmos-odm
   ```

2. **Install in editable mode** (recommended for development/testing):
   ```bash
   pip install -e .
   ```
   
   This installs the package in "editable" mode, meaning:
   - Changes to the source code are immediately reflected
   - The package behaves as if installed from PyPI
   - All dependencies are automatically installed

3. **Alternative: Direct installation**:
   ```bash
   pip install .
   ```

### Verify Installation

Test that the package is working correctly:

```python
import cosmos_odm
from cosmos_odm import Document, container, PK, CosmosClientManager

print(f"✅ cosmos-odm version: {cosmos_odm.__version__}")
```

### Future PyPI Release

Once the package is stabilized and published to PyPI, installation will be simplified to:

```bash
pip install cosmos-odm  # Coming soon!
```

## Quick Start

> **📝 Note**: Make sure you've completed the [Installation](#installation) steps above before trying these examples.

### Define Your Document Model

```python
from pydantic import Field
from cosmos_odm import Document, container, PK, ETag
from typing import List

@container(
    name="documents",
    partition_key_path="/tenantId",
    ttl=30*24*3600,  # 30 days TTL
    vector_policy=[{
        "path": "/content_vector", 
        "dataType": "float32", 
        "dimensions": 1536
    }],
    vector_indexes=[{
        "path": "/content_vector", 
        "type": "flat"
    }],
    full_text_indexes=[{
        "paths": ["/title", "/content"]
    }]
)
class Document(Document):
    id: str
    tenantId: PK[str] = Field(serialization_alias="tenantId")
    title: str
    content: str
    content_vector: List[float] | None = None
    status: str = "draft"
    etag: ETag | None = None
```

### Basic CRUD Operations

```python
import asyncio
from cosmos_odm import CosmosClientManager

async def main():
    # Initialize client
    client_manager = CosmosClientManager(
        connection_string="AccountEndpoint=https://..."
    )
    
    # Bind to collection
    docs = await Document.bind(
        database="myapp",
        client_manager=client_manager
    )
    
    # Ensure indexes are provisioned
    await docs.ensure_indexes()
    
    # Create document
    doc = Document(
        id="doc-1",
        tenantId=PK("tenant-1"),
        title="Introduction to Vector Search",
        content="Vector search enables semantic similarity...",
        content_vector=[0.1, 0.2, 0.3, ...]  # 1536 dimensions
    )
    
    created_doc = await docs.create(doc)
    print(f"Created with RU: {created_doc._ru_metrics.request_charge}")
    
    # Point read (most efficient)
    doc = await docs.get(pk="tenant-1", id="doc-1")
    
    # Conditional update with ETag
    doc.status = "published"
    updated_doc = await docs.replace(doc, if_match=doc.etag.value)
    
    # Delete
    await docs.delete(pk="tenant-1", id="doc-1")

asyncio.run(main())
```

## Native Search Examples

### Vector Search

```python
# Semantic similarity search
my_query_vector = [0.1, 0.2, 0.3, ...]  # From your embedding model

results = await docs.vector_search(
    vector=my_query_vector,
    vector_path="/content_vector",
    k=10,
    filter={"status": "published"},
    partition_key="tenant-1"  # Optional: single-partition search
)

for doc in results.items:
    print(f"Found: {doc.title} (Score: {results.scores[0] if results.scores else 'N/A'})")
print(f"Search cost: {results.ru_metrics.request_charge} RU")
```

### Full-Text Search (BM25)

```python
# Keyword-based search with BM25 ranking
results = await docs.full_text_search(
    text="machine learning algorithms",
    fields=["/title", "/content"],
    k=10,
    filter={"status": "published"}
)

for doc in results.items:
    print(f"Found: {doc.title}")
```

### Hybrid Search (RRF Fusion)

```python
# Best of both worlds: semantic + keyword search
results = await docs.hybrid_search(
    text="machine learning vector search",
    vector=my_query_vector,
    fields=["/title", "/content"],
    vector_path="/content_vector",
    k=10,
    weights=[2, 1],  # Favor text over vector
    filter={"status": "published"}
)

for doc in results.items:
    print(f"Hybrid result: {doc.title}")
```

## Generated SQL Examples

The ODM generates optimized Cosmos SQL queries:

### Vector Search SQL
```sql
SELECT TOP @k c
FROM c
WHERE c.status = @status
ORDER BY RANK VectorDistance(c/content_vector, @vector)
```

### Full-Text Search SQL
```sql
SELECT TOP @k c  
FROM c
WHERE c.status = @status
ORDER BY RANK FullTextScore(c/title, @text) + FullTextScore(c/content, @text)
```

### Hybrid Search SQL
```sql
SELECT TOP @k c
FROM c  
WHERE c.status = @status
ORDER BY RANK RRF(
    FullTextScore(c/content, @text), 
    VectorDistance(c/content_vector, @vector), 
    @weights
)
```

## Advanced Features

### Query with Pagination

```python
async def paginated_search():
    continuation = None
    page_num = 0
    
    while True:
        async for page in docs.query(
            sql="SELECT * FROM c WHERE c.status = @status",
            parameters={"status": "published"},
            partition_key="tenant-1",
            max_item_count=100,
            continuation_token=continuation
        ):
            page_num += 1
            print(f"Page {page_num}: {len(page.items)} items, {page.ru_metrics.request_charge} RU")
            
            for doc in page.items:
                print(f"  - {doc.title}")
            
            continuation = page.continuation_token
            if not continuation:
                return
            break
```

### Transactional Batches

```python
# All operations succeed or fail together within a partition
async with docs.batch(pk="tenant-1") as batch:
    await batch.create(doc1)
    await batch.replace(doc2)
    await batch.delete("doc-3")
# Automatically committed on exit
```

### Patch Operations

```python
from cosmos_odm.types import PatchOp

# Efficient partial updates
await docs.patch(
    pk="tenant-1",
    id="doc-1", 
    operations=[
        PatchOp(op="replace", path="/status", value="archived"),
        PatchOp(op="set", path="/archived_at", value="2024-01-01T00:00:00Z"),
        PatchOp(op="incr", path="/view_count", value=1)
    ],
    if_match=current_etag
)
```

## Indexing Policy Setup

### Vector Indexes

The ODM automatically provisions vector embedding policies and indexes:

```python
# Vector policy defines the embedding specification
vector_policy = [{
    "path": "/content_vector",
    "dataType": "float32",      # or "float16", "int8"  
    "dimensions": 1536,
    "distanceFunction": "cosine"  # or "euclidean", "dotproduct"
}]

# Vector indexes define search optimization
vector_indexes = [{
    "path": "/content_vector",
    "type": "flat"              # or "quantizedFlat", "diskAnn"
}]
```

### Full-Text Indexes

```python
# Enable BM25 search on specified paths
full_text_indexes = [{
    "paths": ["/title", "/content", "/summary"]
}]
```

Call `await docs.ensure_indexes()` to apply these policies idempotently.

## Performance Notes

### Vector Index Types
- **`flat`**: Exact search, highest accuracy, moderate performance
- **`quantizedFlat`**: Quantized vectors, good balance of speed/accuracy
- **`diskAnn`**: Approximate search, highest performance, slight accuracy trade-off

### RU Consumption Patterns
- **Point reads**: ~1 RU (most efficient)
- **Vector search**: 5-50+ RU depending on dimensions, index type, result count
- **Full-text search**: 3-20+ RU depending on text complexity, result count  
- **Hybrid search**: 8-70+ RU (combines both search costs)

### Partition Strategy
- **Single-partition searches** are more efficient (specify `partition_key`)
- **Cross-partition searches** work but consume more RUs
- Design partition keys to enable partition-local search when possible

## Error Handling

```python
from cosmos_odm import (
    ConditionalCheckFailed, 
    ThroughputExceeded, 
    VectorIndexMissing,
    FullTextIndexMissing
)

try:
    await docs.vector_search(vector=my_vector)
except VectorIndexMissing as e:
    print(f"Missing vector index: {e.remediation}")
    await docs.ensure_indexes()  # Fix the issue
    
except ThroughputExceeded as e:
    print(f"Rate limited. Retry after {e.retry_after_ms}ms")
    
except ConditionalCheckFailed:
    print("ETag mismatch - document was modified")
```

## Development & Testing

### Running Tests

The package includes comprehensive tests that work with both the Cosmos DB Local Emulator and Azure Cosmos DB cloud instances.

**Prerequisites for testing**:
- Install [Cosmos DB Local Emulator](https://docs.microsoft.com/en-us/azure/cosmos-db/local-emulator) for local testing
- Or set up an Azure Cosmos DB account for cloud testing

**Run the test suite**:
```bash
# Install test dependencies
pip install -e ".[test]"

# Run all tests (uses local emulator by default)
pytest tests/ -v

# Run tests against Azure Cosmos DB cloud (requires authentication)
export AZURE_COSMOSDB_ENDPOINT="https://your-account.documents.azure.com:443/"
pytest tests/ -v
```

**Example scripts**: Check the `examples/` directory for real-world usage patterns:
- `examples/demo_integration.py` - Basic ODM operations
- `examples/document_management.py` - Advanced document management system

### Contributing

This is an experimental package under active development. Contributions, feedback, and bug reports are welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests to ensure everything works
5. Submit a pull request

## Limitations & Troubleshooting

### Current Limitations
- **Experimental status**: API may change before stable release
- Vector search requires Azure Cosmos DB for NoSQL with vector preview enabled
- Full-text search requires Cosmos DB accounts with full-text search preview
- Maximum vector dimensions: 2000 (varies by region/account)
- RRF hybrid search may not be available in all regions yet

### Troubleshooting
1. **Package import fails**: Ensure you've installed with `pip install -e .`
2. **Vector search fails**: Ensure vector policy + index are configured correctly
3. **Full-text search fails**: Verify full-text index covers the searched paths  
4. **High RU consumption**: Consider using single-partition searches, quantized indexes
5. **Index provisioning errors**: Check account features and regional availability

## Sync Interface

For non-async environments, use the sync facade:

```python
from cosmos_odm.sync import Collection as SyncCollection

# Sync operations mirror async API
docs_sync = SyncCollection.from_async(docs)
doc = docs_sync.get(pk="tenant-1", id="doc-1")
results = docs_sync.vector_search(vector=my_vector, k=10)
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/

# Linting and formatting
ruff check src/ tests/
black src/ tests/
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality  
4. Ensure all tests pass and type checking is clean
5. Submit a pull request

---

**Note**: This ODM requires Azure Cosmos DB for NoSQL with vector and full-text search preview features enabled. Check the [Azure documentation](https://docs.microsoft.com/azure/cosmos-db/) for the latest availability and setup instructions.