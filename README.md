# Cosmos ODM

A production-grade, async-first **Azure Cosmos DB NoSQL ODM** for Python with native **vector search**, **full-text search**, and **hybrid search** capabilities built directly into Azure Cosmos DB for NoSQL.

> **⚠️ Experimental Package**: This package is currently experimental and has not yet been published to PyPI. See [Installation](#installation) section for local testing instructions.

## Features

### 🚀 **Core ODM Capabilities**
- **Async-first** with optional sync facade
- **Advanced CRUD operations**: smart save, replace, sync with conflict resolution
- **Document state management**: change tracking, rollback, optimized updates
- **Type-safe query builder**: fluent interface with method chaining and SQL generation
- **Bulk operations**: efficient batch processing with BulkWriter for high-throughput
- **Pydantic v2** models with full validation and type safety

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
- **Request Unit (RU) telemetry** on every operation

## Installation

> **🧪 Experimental Installation**: This package is not yet available on PyPI. To test the package locally, you'll need to install it directly from the source code.

### Prerequisites
- Python 3.11 or higher
- Git (for cloning the repository)
- Azure CLI (for DefaultAzureCredential authentication) - run `az login` first

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
        "data_type": "float32", 
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
class MyDocument(Document):
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
    # Option 1: Initialize client with connection string
    client_manager = CosmosClientManager(
        connection_string="AccountEndpoint=https://..."
    )
    
    # Option 2: Initialize client with endpoint and DefaultAzureCredential
    # (Recommended for production - uses managed identity, service principal, etc.)
    # Make sure you're authenticated with Azure CLI: az login
    client_manager = CosmosClientManager(
        endpoint="https://your-account.documents.azure.com:443/",
        key=None  # Explicitly set to None to avoid environment variable interference
        # No key needed - automatically uses DefaultAzureCredential
    )
    
    # Option 3: Initialize client with endpoint and key
    # client_manager = CosmosClientManager(
    #     endpoint="https://your-account.documents.azure.com:443/",
    #     key="your-account-key"
    # )
    
    # Bind to collection
    docs = await MyDocument.bind(
        database="myapp",
        client_manager=client_manager
    )
    
    # Ensure indexes are provisioned
    await docs.ensure_indexes()
    
    # Create document
    doc = MyDocument(
        id="doc-1",
        tenantId=PK("tenant-1"),
        title="Introduction to Vector Search",
        content="Vector search enables semantic similarity...",
        content_vector=[0.1, 0.2, 0.3, ...]  # 1536 dimensions
    )
    
    created_doc = await docs.create(doc)
    print(f"Created document: {created_doc.id}")
    
    # Check if RU metrics are available
    if hasattr(created_doc, '_ru_metrics') and created_doc._ru_metrics:
        print(f"Request charge: {created_doc._ru_metrics.request_charge} RU")
    
    # Point read (most efficient)
    doc = await docs.get(pk="tenant-1", id="doc-1")
    
    # Conditional update with ETag
    doc.status = "published"
    updated_doc = await docs.replace(doc, if_match=doc.etag.value)
    
    # Delete
    await docs.delete(pk="tenant-1", id="doc-1")

asyncio.run(main())
```

## Key Features

This ODM provides advanced capabilities including smart CRUD operations with conflict resolution, document state management with change tracking, type-safe query builder interface, bulk operations for high-throughput processing, and comprehensive search features.

📖 **[See detailed documentation](docs/README.md)** for all features.

## Authentication Options

The Cosmos ODM supports multiple authentication methods for connecting to Azure Cosmos DB:

### 1. DefaultAzureCredential (Recommended for Production)

Uses Azure's DefaultAzureCredential which automatically tries various authentication methods in order:

```python
from cosmos_odm import CosmosClientManager

# Automatically uses DefaultAzureCredential
client_manager = CosmosClientManager(
    endpoint="https://your-account.documents.azure.com:443/",
    key=None  # Explicitly set to None
)
```

**Authentication chain (in order of precedence):**
1. **Azure CLI** - if you've run `az login`
2. **Managed Identity** - for Azure services (VMs, App Service, Functions, etc.)
3. **Visual Studio Code** - if logged in through Azure extension
4. **Service Principal** - using environment variables:
   - `AZURE_CLIENT_ID`
   - `AZURE_CLIENT_SECRET` 
   - `AZURE_TENANT_ID`

**Setup examples:**
```bash
# For local development - Azure CLI
az login

# For Azure services - enable Managed Identity in Azure portal
# No additional setup needed - automatically detected

# For CI/CD or server applications - Service Principal
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret" 
export AZURE_TENANT_ID="your-tenant-id"
```

### 2. Connection String

Simplest method for development and testing:

```python
client_manager = CosmosClientManager(
    connection_string="AccountEndpoint=https://your-account.documents.azure.com:443/;AccountKey=your-key==;"
)
```

### 3. Account Key

Direct key-based authentication:

```python
client_manager = CosmosClientManager(
    endpoint="https://your-account.documents.azure.com:443/",
    key="your-account-key"
)
```

### Authentication Troubleshooting

If you encounter authentication issues:

1. **For Azure CLI**: Run `az login` first
2. **For Service Principal**: Ensure environment variables are set correctly
3. **For Managed Identity**: Verify identity is assigned to your Azure resource
4. **Environment Variables**: Avoid conflicts - explicitly set `key=None` when using DefaultAzureCredential

**Note**: The `azure-identity` package is automatically installed as a dependency for DefaultAzureCredential support.

## Examples

### Smart CRUD with State Management

```python
# Enable automatic change tracking
@container(name="documents", partition_key_path="/tenantId")
class TrackedDocument(Document):
    # ... fields ...
    class Config:
        state_management = True

# Smart save with change detection
doc.title = "Updated Title"
if doc.is_changed:
    await docs.save_changes(doc)  # Only sends changed fields
```

### Type-Safe Query Building

```python
# Fluent query interface
results = await docs.find() \
    .where("status").equals("published") \
    .where("rating").greater_than(4.0) \
    .order_by("created_date", ascending=False) \
    .limit(10) \
    .to_list()
```

### Bulk Operations

```python
# High-throughput batch processing with configurable concurrency
from cosmos_odm import BulkWriter

# Create BulkWriter with custom concurrency limit
bulk = BulkWriter(docs, max_concurrency=20)  # Default is 10

# Queue multiple operations
for doc in large_document_list:
    bulk.insert(doc)

# Execute with progress tracking
def progress_callback(completed, total):
    print(f"Progress: {completed}/{total} ({completed/total*100:.1f}%)")

results = await bulk.execute(
    progress_callback=progress_callback,
    batch_size=100  # Report progress every 100 operations
)

# Check results
successful = [r for r in results if r["success"]]
failed = [r for r in results if not r["success"]]
print(f"✅ {len(successful)} successful, ❌ {len(failed)} failed")
```

## Native Search Examples

This ODM provides powerful search capabilities built directly into Azure Cosmos DB:

### Vector Search
```python
# Semantic similarity search
my_query_vector = [0.1, 0.2, 0.3, ...]  # From your embedding model

similar_docs = await docs.vector_search(
    vector=my_query_vector,
    k=10,
    similarity_score_threshold=0.8
)
```

### Full-Text Search  
```python
# BM25-based text search
search_results = await docs.full_text_search(
    query="machine learning python",
    k=15
)
```

### Hybrid Search
```python
# Combined vector + text search using RRF
hybrid_results = await docs.hybrid_search(
    text_query="machine learning",
    vector=my_query_vector,
    k=10,
    alpha=0.6  # Balance between vector (0.6) and text (0.4)
)
```

📖 **[See complete search documentation](docs/search.md)** for vector embeddings, full-text indexing, hybrid search patterns, and performance optimization.

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
    "data_type": "float32",      # or "float16", "int8"  
    "dimensions": 1536,
    "distance_function": "cosine"  # or "euclidean", "dotproduct"
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
from cosmos_odm import NotFound, ConditionalCheckFailed

try:
    doc = await docs.get(pk="tenant-1", id="nonexistent")
except NotFound:
    print("Document not found")

try:
    await docs.replace(doc, if_match="outdated-etag")
except ConditionalCheckFailed:
    print("Document was modified by another process")
```

## Development & Testing

### Running Tests

Run the comprehensive test suite covering all features:

```bash
# Install test dependencies
pip install -e ".[test]"

# Run all tests (uses local emulator by default)
pytest tests/ -v

# Run tests against Azure Cosmos DB cloud
export AZURE_COSMOSDB_ENDPOINT="https://your-account.documents.azure.com:443/"
pytest tests/ -v
```

**Prerequisites**: Install [Cosmos DB Local Emulator](https://docs.microsoft.com/en-us/azure/cosmos-db/local-emulator) or set up an Azure Cosmos DB account.

### Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Type checking
mypy src/

# Linting and formatting
ruff check src/ tests/
black src/ tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch  
3. Add tests for new functionality
4. Ensure all tests pass and type checking is clean
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file.

---

**Note**: This ODM requires Azure Cosmos DB for NoSQL with vector and full-text search preview features enabled. Check the [Azure documentation](https://docs.microsoft.com/azure/cosmos-db/) for the latest availability and setup instructions.

### Recent Updates

- **Authentication Enhancements**: Added comprehensive support for DefaultAzureCredential with automatic fallback chain
- **Index Management**: Fixed container indexing operations to properly preserve partition key configurations  
- **Dependencies**: Added azure-identity package for production-ready authentication
- **Documentation**: Enhanced authentication guide with troubleshooting and multiple deployment scenarios