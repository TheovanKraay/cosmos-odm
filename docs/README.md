# Cosmos ODM Documentation

Welcome to the comprehensive documentation for the Cosmos ODM (Object Document Mapper) for Azure Cosmos DB.

## Getting Started

- [Installation and Quick Start](../README.md) - Basic setup and first steps
- [API Reference](api-reference.md) - Complete method signatures and configuration options

## Core Features

### Enhanced Document Operations
- [Enhanced CRUD Operations](enhanced-crud.md) - Advanced save, replace, sync operations with conflict resolution
- [Document State Management](state-management.md) - Change tracking, rollback, and optimized updates

### Query and Search
- [Type-Safe Query Interface](query-interface.md) - Fluent query builder with method chaining
- [Search Features](search.md) - Vector search, full-text search, and hybrid search capabilities

### Performance and Scalability
- [Bulk Operations](bulk-operations.md) - Efficient batch processing with BulkWriter

## Feature Comparison

| Feature | Basic ODM | Enhanced ODM | Benefits |
|---------|-----------|--------------|----------|
| Document CRUD | ✅ create, get, replace, delete | ✅ + save, sync, merge strategies | Smart operations, conflict resolution |
| State Management | ❌ Manual tracking | ✅ Automatic change detection | Optimized updates, reduced RU consumption |
| Query Interface | ❌ Raw SQL only | ✅ Type-safe fluent API | IDE support, SQL generation, readability |
| Bulk Operations | ❌ Manual batching | ✅ BulkWriter + collection methods | High-throughput, error handling |
| Search | ✅ Basic vector/text | ✅ + hybrid search, advanced filtering | Better relevance, complex queries |

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
├─────────────────────────────────────────────────────────────┤
│  Enhanced CRUD    │  Query Builder  │  State Management    │
│  - save()         │  - find()       │  - change tracking   │
│  - sync()         │  - where()      │  - rollback()        │
│  - merge()        │  - order_by()   │  - get_changes()     │
├─────────────────────────────────────────────────────────────┤
│  Search Features  │  Bulk Operations │  Document Models     │
│  - vector_search  │  - BulkWriter   │  - Pydantic v2      │
│  - full_text      │  - insert_many  │  - Type safety       │
│  - hybrid_search  │  - delete_many  │  - Validation        │
├─────────────────────────────────────────────────────────────┤
│                     Core ODM Layer                          │
│  Collection Management │ Index Management │ Client Management │
├─────────────────────────────────────────────────────────────┤
│                  Azure Cosmos DB SDK                        │
│  Native Vector Search │ Full-Text Search │ SQL API            │
└─────────────────────────────────────────────────────────────┘
```

## Quick Navigation

### By Use Case

**Content Management**
- [Enhanced CRUD](enhanced-crud.md) for document lifecycle management
- [Search Features](search.md) for content discovery
- [State Management](state-management.md) for editing workflows

**Data Processing**
- [Bulk Operations](bulk-operations.md) for high-throughput scenarios
- [Query Interface](query-interface.md) for complex data retrieval
- [API Reference](api-reference.md) for performance optimization

**AI/ML Applications**
- [Search Features](search.md) for vector embeddings and semantic search
- [Query Interface](query-interface.md) for training data selection
- [Bulk Operations](bulk-operations.md) for model inference pipelines

### By Experience Level

**Beginners**
1. Start with [README Quick Start](../README.md#quick-start)
2. Learn [Enhanced CRUD Operations](enhanced-crud.md)
3. Explore [Query Interface](query-interface.md)

**Intermediate**
1. Master [State Management](state-management.md)
2. Implement [Search Features](search.md)
3. Optimize with [Bulk Operations](bulk-operations.md)

**Advanced**
1. Deep dive into [API Reference](api-reference.md)
2. Performance tuning and optimization
3. Custom extensions and integrations

## Examples and Patterns

Each documentation page includes:
- **Basic usage examples** for getting started
- **Advanced patterns** for complex scenarios
- **Performance optimization** tips and best practices
- **Real-world applications** and use cases
- **Cross-references** to related features

## Contributing

Found an issue or want to improve the documentation?
1. Fork the repository
2. Make your changes
3. Submit a pull request

For questions or discussions, please open an issue in the repository.

---

**Note**: This ODM requires Azure Cosmos DB for NoSQL with vector and full-text search preview features enabled. Check the [Azure documentation](https://docs.microsoft.com/azure/cosmos-db/) for the latest availability and setup instructions.