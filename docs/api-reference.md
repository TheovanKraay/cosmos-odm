# API Reference

Complete API reference for the Cosmos ODM, including all classes, methods, and configuration options.

## Document Class

### Core Document Methods

```python
class Document(BaseModel):
    """Base document class for Cosmos ODM"""
    
    # Core identification
    id: str
    etag: ETag | None = None
    
    # State management
    def _enable_state_management(self) -> None:
        """Enable change tracking for this document instance"""
    
    def _disable_state_management(self) -> None:
        """Disable change tracking and free memory"""
    
    @property
    def is_changed(self) -> bool:
        """Check if document has any local changes"""
    
    def get_changes(self) -> Dict[str, Any]:
        """Get dictionary of changed fields and their new values"""
    
    def rollback(self) -> None:
        """Revert all local changes to original state"""
    
    # Serialization
    def model_dump_cosmos(self) -> Dict[str, Any]:
        """Serialize document for Cosmos DB storage"""
    
    @classmethod
    def model_validate_cosmos(cls, data: Dict[str, Any]) -> 'Document':
        """Deserialize document from Cosmos DB data"""
```

## Collection Class

### CRUD Operations

```python
class Collection:
    """Collection interface for document operations"""
    
    # Basic CRUD
    async def create(
        self, 
        document: Document,
        partition_key: Any = None,
        **kwargs
    ) -> Document:
        """Create a new document"""
    
    async def get(
        self,
        pk: Any,
        id: str,
        consistency_level: str = None,
        **kwargs
    ) -> Document | None:
        """Get document by partition key and id"""
    
    async def replace(
        self,
        document: Document,
        if_match: str = None,
        if_none_match: str = None,
        **kwargs
    ) -> Document:
        """Replace entire document"""
    
    async def delete(
        self,
        pk: Any,
        id: str,
        if_match: str = None,
        **kwargs
    ) -> None:
        """Delete document by partition key and id"""
    
    # Advanced CRUD
    async def save(
        self,
        document: Document,
        merge_strategy: MergeStrategy = MergeStrategy.REPLACE_ENTIRE,
        if_match: str = None,
        **kwargs
    ) -> Document:
        """Smart save - create or update document"""
    
    async def save_changes(
        self,
        document: Document,
        **kwargs
    ) -> Document:
        """Save only changed fields (requires state management)"""
    
    async def replace_document(
        self,
        document: Document,
        merge_strategy: MergeStrategy = MergeStrategy.REPLACE_ENTIRE,
        if_match: str = None,
        **kwargs
    ) -> Document:
        """Advanced replace with conflict resolution"""
    
    async def sync_document(
        self,
        document: Document,
        **kwargs
    ) -> Document:
        """Fetch latest version from server"""
```

### Query Operations

```python
    # Query interface
    def find(self) -> QueryBuilder:
        """Create new query builder"""
    
    async def find_one(
        self,
        filter_dict: Dict[str, Any] = None,
        **kwargs
    ) -> Document | None:
        """Find single document matching criteria"""
    
    async def count_documents(
        self,
        filter_dict: Dict[str, Any] = None,
        **kwargs
    ) -> int:
        """Count documents matching criteria"""
    
    async def exists(
        self,
        filter_dict: Dict[str, Any] = None,
        **kwargs
    ) -> bool:
        """Check if any documents match criteria"""
```

### Bulk Operations

```python
    # Bulk operations
    async def insert_many(
        self,
        documents: List[Document],
        batch_size: int = 100,
        **kwargs
    ) -> List[Document]:
        """Insert multiple documents in batches"""
    
    async def update_many(
        self,
        query: QueryBuilder,
        update_fields: Dict[str, Any],
        batch_size: int = 100,
        **kwargs
    ) -> int:
        """Update multiple documents matching query"""
    
    async def delete_many(
        self,
        query: QueryBuilder,
        batch_size: int = 100,
        **kwargs
    ) -> int:
        """Delete multiple documents matching query"""
```

### Search Operations

```python
    # Vector search
    async def vector_search(
        self,
        vector: List[float],
        k: int = 10,
        similarity_score_threshold: float = None,
        where_clause: str = None,
        partition_key: Any = None,
        distance_function: str = "cosine",
        include_embeddings: bool = False,
        **kwargs
    ) -> List[Document]:
        """Perform vector similarity search"""
    
    # Full-text search
    async def full_text_search(
        self,
        query: str,
        k: int = 10,
        where_clause: str = None,
        boost_fields: Dict[str, float] = None,
        match_type: str = "any",
        **kwargs
    ) -> List[Document]:
        """Perform full-text search using BM25"""
    
    # Hybrid search
    async def hybrid_search(
        self,
        text_query: str,
        vector: List[float],
        k: int = 10,
        alpha: float = 0.5,
        where_clause: str = None,
        rrf_constant: int = 60,
        **kwargs
    ) -> List[Document]:
        """Perform hybrid search combining vector and text"""
```

### Index Management

```python
    # Index operations
    async def ensure_indexes(self) -> None:
        """Ensure all configured indexes are created"""
    
    async def create_index(
        self,
        index_definition: Dict[str, Any]
    ) -> None:
        """Create specific index"""
    
    async def drop_index(
        self,
        index_name: str
    ) -> None:
        """Drop specific index"""
    
    async def list_indexes(self) -> List[Dict[str, Any]]:
        """List all indexes for collection"""
```

## Query Builder

### Query Construction

```python
class QueryBuilder:
    """Fluent query builder for type-safe queries"""
    
    # Filtering
    def where(self, field: str) -> FieldQuery:
        """Add filter condition on field"""
    
    def or_where(self, field: str) -> FieldQuery:
        """Add OR filter condition on field"""
    
    # Sorting
    def order_by(
        self,
        field: str,
        ascending: bool = True
    ) -> 'QueryBuilder':
        """Add sorting by field"""
    
    # Pagination
    def skip(self, count: int) -> 'QueryBuilder':
        """Skip number of results"""
    
    def limit(self, count: int) -> 'QueryBuilder':
        """Limit number of results"""
    
    # Execution
    async def to_list(self) -> List[Document]:
        """Execute query and return all results"""
    
    async def first(self) -> Document | None:
        """Execute query and return first result"""
    
    async def count(self) -> int:
        """Execute query and return count"""
    
    async def exists(self) -> bool:
        """Execute query and check if any results exist"""
    
    # Utility
    def to_sql(self) -> str:
        """Generate SQL query string"""
    
    def get_query_info(self) -> Dict[str, Any]:
        """Get query execution information"""
```

### Field Query Conditions

```python
class FieldQuery:
    """Field-specific query conditions"""
    
    # Equality
    def equals(self, value: Any) -> QueryBuilder:
        """Field equals value"""
    
    def not_equals(self, value: Any) -> QueryBuilder:
        """Field does not equal value"""
    
    # Comparison
    def greater_than(self, value: Any) -> QueryBuilder:
        """Field greater than value"""
    
    def greater_than_or_equal(self, value: Any) -> QueryBuilder:
        """Field greater than or equal to value"""
    
    def less_than(self, value: Any) -> QueryBuilder:
        """Field less than value"""
    
    def less_than_or_equal(self, value: Any) -> QueryBuilder:
        """Field less than or equal to value"""
    
    def between(self, min_val: Any, max_val: Any) -> QueryBuilder:
        """Field between min and max values"""
    
    # String operations
    def contains(self, substring: str) -> QueryBuilder:
        """Field contains substring"""
    
    def starts_with(self, prefix: str) -> QueryBuilder:
        """Field starts with prefix"""
    
    def ends_with(self, suffix: str) -> QueryBuilder:
        """Field ends with suffix"""
    
    # Array operations
    def in_values(self, values: List[Any]) -> QueryBuilder:
        """Field value in list of values"""
    
    def not_in(self, values: List[Any]) -> QueryBuilder:
        """Field value not in list of values"""
    
    # Null checks
    def is_null(self) -> QueryBuilder:
        """Field is null"""
    
    def is_not_null(self) -> QueryBuilder:
        """Field is not null"""
    
    # Array functions
    def array_length(self) -> 'ArrayLengthQuery':
        """Array length operations"""
```

## Bulk Writer

### Bulk Operations

```python
class BulkWriter:
    """Efficient bulk operation writer"""
    
    def __init__(
        self,
        collection: Collection,
        batch_size: int = 100
    ):
        """Initialize bulk writer"""
    
    # Operation queuing
    def insert(self, document: Document) -> None:
        """Queue document for insertion"""
    
    def update(self, document: Document) -> None:
        """Queue document for update"""
    
    def delete(self, document: Document) -> None:
        """Queue document for deletion"""
    
    def upsert(self, document: Document) -> None:
        """Queue document for upsert"""
    
    # Execution
    async def execute(self) -> List[Document]:
        """Execute all queued operations"""
    
    # Status
    def has_operations(self) -> bool:
        """Check if any operations are queued"""
    
    def operation_count(self) -> int:
        """Get number of queued operations"""
    
    def clear(self) -> None:
        """Clear all queued operations"""
```

## Configuration Classes

### Container Decorator

```python
@container(
    name: str,                              # Container name
    database: str = None,                   # Database name
    partition_key_path: str = "/id",        # Partition key path
    ttl: int = None,                        # Time to live in seconds
    vector_policy: List[Dict] = None,       # Vector policy configuration
    vector_indexes: List[Dict] = None,      # Vector index configuration
    full_text_indexes: List[Dict] = None,   # Full-text index configuration
    unique_keys: List[Dict] = None,         # Unique key constraints
    indexing_mode: str = "consistent",      # Indexing mode
    automatic_indexing: bool = True         # Automatic indexing
)
class MyDocument(Document):
    # Document fields
    pass
```

### Vector Policy Configuration

```python
# Vector policy configuration
vector_policy = [
    {
        "path": "/embedding",               # Field path
        "dataType": "float32",              # Data type (float32, float16, uint8)
        "dimensions": 1536,                 # Vector dimensions
        "distanceFunction": "cosine"        # Distance function
    }
]

# Vector index configuration
vector_indexes = [
    {
        "path": "/embedding",               # Field path
        "type": "flat",                     # Index type (flat, quantizedFlat)
        "quantizationByteSize": 2,          # Quantization (for quantizedFlat)
        "rerankWithOriginalVectors": True   # Rerank with original vectors
    }
]
```

### Full-Text Index Configuration

```python
# Full-text index configuration
full_text_indexes = [
    {
        "paths": ["/title", "/content"],    # Indexed paths
        "analyzer": "standard",             # Text analyzer
        "boost": {                          # Field boosting
            "/title": 2.0,
            "/content": 1.0
        }
    }
]
```

## Merge Strategies

```python
class MergeStrategy(Enum):
    """Document merge strategies for conflict resolution"""
    
    REPLACE_ENTIRE = "replace_entire"       # Replace entire document (default)
    MERGE_FIELDS = "merge_fields"           # Merge non-null fields
    PREFER_NEWER = "prefer_newer"           # Use newer document by timestamp
    PREFER_EXISTING = "prefer_existing"     # Keep existing document
```

## Type Aliases and Helper Types

### Partition Key Types

```python
class PK(Generic[T]):
    """Partition key wrapper for type safety"""
    
    def __init__(self, value: T):
        self.value = value
    
    def __str__(self) -> str:
        return str(self.value)
    
    def __repr__(self) -> str:
        return f"PK({self.value!r})"
```

### ETag Types

```python
class ETag:
    """ETag wrapper for optimistic concurrency"""
    
    def __init__(self, value: str):
        self.value = value
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"ETag({self.value!r})"
```

## Client Management

### CosmosClientManager

```python
class CosmosClientManager:
    """Manages Cosmos DB client connections with multiple authentication methods"""
    
    def __init__(
        self,
        connection_string: str = None,
        endpoint: str = None,
        key: str = None,
        credential: Any = None,
        database_name: str = None,
        consistency_level: str = "Session",
        **kwargs
    ):
        """Initialize client manager with flexible authentication options
        
        Authentication Options (in order of precedence):
        1. connection_string - Complete connection string with endpoint and key
        2. credential - Custom Azure credential object
        3. key - Account key (requires endpoint)
        4. DefaultAzureCredential - Automatic credential detection (when key=None)
        
        Args:
            connection_string: Full Cosmos DB connection string
            endpoint: Cosmos DB account endpoint URL
            key: Account key (set to None to use DefaultAzureCredential)
            credential: Custom Azure credential object
            database_name: Default database name
            consistency_level: Default consistency level ("Session", "Strong", etc.)
            
        Examples:
            # Connection string
            client = CosmosClientManager(
                connection_string="AccountEndpoint=https://...;AccountKey=...;"
            )
            
            # DefaultAzureCredential (recommended for production)
            client = CosmosClientManager(
                endpoint="https://your-account.documents.azure.com:443/",
                key=None  # Triggers DefaultAzureCredential
            )
            
            # Account key
            client = CosmosClientManager(
                endpoint="https://your-account.documents.azure.com:443/",
                key="your-account-key"
            )
        """
    
    @property
    def async_client(self) -> AsyncCosmosClient:
        """Get async Cosmos client instance"""
    
    @property  
    def sync_client(self) -> CosmosClient:
        """Get sync Cosmos client instance"""
        
    def get_database(self, database_name: str = None) -> AsyncDatabaseProxy:
        """Get async database proxy"""
    
    def get_async_container(
        self,
        database_name: str,
        container_name: str
    ) -> AsyncContainerProxy:
        """Get async container proxy"""
        
    def get_sync_container(
        self,
        database_name: str, 
        container_name: str
    ) -> ContainerProxy:
        """Get sync container proxy"""
    
    async def close(self) -> None:
        """Close all connections and cleanup resources"""
```

## Exception Classes

### ODM Exceptions

```python
class CosmosODMError(Exception):
    """Base exception for Cosmos ODM"""
    pass

class DocumentNotFoundError(CosmosODMError):
    """Document not found exception"""
    pass

class ConflictError(CosmosODMError):
    """Document conflict exception"""
    pass

class ValidationError(CosmosODMError):
    """Document validation exception"""
    pass

class BulkOperationError(CosmosODMError):
    """Bulk operation exception"""
    
    def __init__(
        self,
        message: str,
        partial_results: List[Document] = None,
        failed_operations: List[Dict] = None
    ):
        self.partial_results = partial_results or []
        self.failed_operations = failed_operations or []
        super().__init__(message)
```

## Utility Functions

### Document Binding

```python
# Document class binding
async def bind_document_class(
    document_class: Type[Document],
    database: str,
    client_manager: CosmosClientManager,
    **kwargs
) -> Collection:
    """Bind document class to collection"""

# Usage
docs = await MyDocument.bind(
    database="myapp",
    client_manager=client_manager
)
```

### Index Utilities

```python
# Index management utilities
async def ensure_container_indexes(
    container_client: ContainerProxy,
    vector_policy: List[Dict] = None,
    vector_indexes: List[Dict] = None,
    full_text_indexes: List[Dict] = None
) -> None:
    """Ensure all indexes are created"""

async def optimize_indexes(
    container_client: ContainerProxy
) -> Dict[str, Any]:
    """Optimize existing indexes"""
```

## Configuration Options

### Global Configuration

```python
# Global ODM configuration
from cosmos_odm import configure

configure(
    default_consistency_level="Session",
    enable_request_unit_tracking=True,
    enable_state_management_by_default=False,
    default_batch_size=100,
    connection_pool_size=10,
    request_timeout=30,
    retry_total=3,
    retry_backoff_factor=0.3
)
```

### Environment Variables

```bash
# Cosmos DB connection
AZURE_COSMOSDB_ENDPOINT="https://account.documents.azure.com:443/"
AZURE_COSMOSDB_KEY="primary-key"
AZURE_COSMOSDB_CONNECTION_STRING="AccountEndpoint=...;AccountKey=...;"

# ODM configuration
COSMOS_ODM_CONSISTENCY_LEVEL="Session"
COSMOS_ODM_ENABLE_RU_TRACKING="true"
COSMOS_ODM_DEFAULT_BATCH_SIZE="100"
COSMOS_ODM_REQUEST_TIMEOUT="30"
```

## Performance Monitoring

### Request Unit Tracking

```python
# RU metrics are available on all document results
result = await docs.create(document)
print(f"RU consumed: {result._ru_metrics.request_charge}")
print(f"Activity ID: {result._ru_metrics.activity_id}")

# Bulk operation RU tracking
results = await docs.insert_many(documents)
total_ru = sum(doc._ru_metrics.request_charge for doc in results)
print(f"Total RU for bulk operation: {total_ru}")
```

### Query Performance

```python
# Query execution metrics
query = docs.find().where("status").equals("published")
query_info = query.get_query_info()

print(f"Estimated RU cost: {query_info.get('estimated_ru')}")
print(f"Index usage: {query_info.get('index_usage')}")
print(f"Cross-partition: {query_info.get('cross_partition')}")
```

This comprehensive API reference covers all major components of the Cosmos ODM. For more detailed examples and usage patterns, see the feature-specific documentation pages.