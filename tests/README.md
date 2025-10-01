# Integration Tests for Cosmos ODM

This directory contains comprehensive integration tests that work against a **Cosmos DB Local Emulator**.

## Prerequisites

### 1. Install Cosmos DB Local Emulator

Download and install from: https://docs.microsoft.com/en-us/azure/cosmos-db/local-emulator

### 2. Start the Emulator

```bash
# Start emulator (Windows)
"C:\Program Files\Azure Cosmos DB Emulator\CosmosDB.Emulator.exe"

# Or from command line with custom settings
"C:\Program Files\Azure Cosmos DB Emulator\CosmosDB.Emulator.exe" /EnableSqlComputeEndpoint /EnableMongoDbEndpoint=3.6
```

The emulator will be available at:
- **Endpoint**: `https://localhost:8081`
- **Account Key**: `C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==`

### 3. Verify Emulator is Running

Open browser to: https://localhost:8081/_explorer/index.html

## Running Integration Tests

### Run All Integration Tests
```bash
cd c:\cosmos\cosmos-python-odm\cosmos-odm
.venv\Scripts\python.exe -m pytest tests/test_integration.py -v
```

### Run Specific Test Categories
```bash
# CRUD operations only
.venv\Scripts\python.exe -m pytest tests/test_integration.py::TestCRUDOperations -v

# Query operations only  
.venv\Scripts\python.exe -m pytest tests/test_integration.py::TestQueryOperations -v

# Search operations only
.venv\Scripts\python.exe -m pytest tests/test_integration.py::TestSearchOperations -v

# Index management only
.venv\Scripts\python.exe -m pytest tests/test_integration.py::TestIndexManagement -v
```

### Run with Coverage
```bash
.venv\Scripts\python.exe -m pytest tests/test_integration.py --cov=cosmos_odm --cov-report=html
```

## Test Structure

### `test_integration.py`
Main integration test suite covering:

#### **TestCRUDOperations**
- ✅ Document creation with automatic ID/timestamp generation
- ✅ Document retrieval by ID and partition key
- ✅ Document updates with ETag handling
- ✅ Document deletion
- ✅ Error handling for missing documents

#### **TestQueryOperations** 
- ✅ Basic SQL queries with pagination
- ✅ Filtered queries using dict filters
- ✅ Parameterized queries
- ✅ RU (Request Unit) tracking and metrics

#### **TestSearchOperations**
- ✅ Vector similarity search (if supported by emulator)
- ✅ Full-text search with BM25 scoring
- ✅ Hybrid search combining vector + text
- ✅ Search result scoring and ranking

#### **TestIndexManagement**
- ✅ Vector index creation and validation
- ✅ Full-text index configuration
- ✅ Index policy management
- ✅ Search capability validation

#### **TestErrorHandling**
- ✅ Connection error handling
- ✅ Malformed document validation
- ✅ Custom ODM exception wrapping

#### **TestRUMetrics**
- ✅ Request Unit consumption tracking
- ✅ Activity ID correlation
- ✅ Performance metrics collection

## Example Documents

### Product Model (with Vector + Full-text Search)
```python
@container(
    name="products",
    partition_key_path="/category_id", 
    vector_policy=[VectorPolicySpec(path="/embedding")],
    vector_indexes=[VectorIndexSpec(path="/embedding")],
    full_text_indexes=[FullTextIndexSpec(paths=["/name", "/description"])]
)
class Product(Document):
    category_id: PK[str]
    name: str
    description: str
    price: float
    embedding: List[float]
    tags: List[str] = []
```

### User Model (Simple CRUD)
```python
@container(name="users", partition_key_path="/tenant_id")
class User(Document):
    tenant_id: PK[str]
    name: str
    email: str
    age: Optional[int] = None
```

## Expected Behavior

### ✅ **What Should Work**
- All CRUD operations (create, read, update, delete)
- SQL queries with filtering and pagination
- RU consumption tracking
- Document validation and serialization
- Error handling and custom exceptions
- Basic container and database management

### ⚠️ **What Might Not Work in Emulator**
- **Vector Search**: Limited support in local emulator
- **Full-text Search**: May not be fully supported
- **Hybrid Search**: Requires both vector + full-text support
- **Advanced Indexing**: Some index types may not be available

The tests include fallback mechanisms and skip unsupported features gracefully.

## Troubleshooting

### Common Issues

1. **SSL Certificate Error**
   ```bash
   # Add to connection string
   DisableSSLVerification=true
   ```

2. **Emulator Not Running**
   ```bash
   # Verify emulator status
   curl -k https://localhost:8081/
   ```

3. **Port Conflicts**
   ```bash
   # Check if port 8081 is in use
   netstat -an | findstr :8081
   ```

4. **Permission Issues**
   - Run emulator as Administrator
   - Check Windows Firewall settings

### Debug Mode
```bash
# Run tests with debug output
.venv\Scripts\python.exe -m pytest tests/test_integration.py -v -s --tb=long
```

## Real-World Examples

See the `examples/` directory for realistic usage scenarios:

- **`demo_integration.py`**: Basic ODM operations with search
- **`document_management.py`**: Advanced document management system

These examples demonstrate production-ready patterns and can be run against the emulator for hands-on testing.