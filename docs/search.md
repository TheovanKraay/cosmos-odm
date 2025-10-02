# Search Features

Azure Cosmos DB's native search capabilities are integrated directly into the ODM, providing powerful vector search, full-text search, and hybrid search functionality without external dependencies.

## Overview

The Cosmos ODM provides three types of native search:

- **Vector Search**: Semantic similarity using embeddings with `VectorDistance()` function
- **Full-Text Search**: BM25-based text search using `FullTextScore()` function  
- **Hybrid Search**: Combined vector and text search using `RRF()` (Reciprocal Rank Fusion)
- **Native indexing**: Vector policies, vector indexes, and full-text indexes

All search capabilities are built into Azure Cosmos DB for NoSQL, requiring no external search services.

## Vector Search

### Document Model Setup

Configure your document model with vector fields and indexes:

```python
from cosmos_odm import Document, container, PK
from typing import List

@container(
    name="documents",
    partition_key_path="/tenantId",
    vector_policy=[{
        "path": "/content_vector", 
        "dataType": "float32", 
        "dimensions": 1536
    }],
    vector_indexes=[{
        "path": "/content_vector", 
        "type": "flat"  # or "quantizedFlat" for larger datasets
    }]
)
class SearchableDocument(Document):
    id: str
    tenantId: PK[str]
    title: str
    content: str
    content_vector: List[float] | None = None
    category: str
```

### Basic Vector Search

Perform semantic similarity searches using embeddings:

```python
# Generate query vector (using your embedding model)
query_text = "machine learning algorithms"
query_vector = await get_embedding(query_text)  # Your embedding function

# Semantic similarity search
similar_docs = await docs.vector_search(
    vector=query_vector,
    k=10,  # Return top 10 results
    similarity_score_threshold=0.7  # Minimum similarity score
)

for doc in similar_docs:
    print(f"Title: {doc.title}")
    print(f"Similarity: {doc._similarity_score}")
    print(f"Content: {doc.content[:100]}...")
```

### Advanced Vector Search

```python
# Vector search with additional filtering
filtered_results = await docs.vector_search(
    vector=query_vector,
    k=20,
    where_clause="c.category = 'technology' AND c.status = 'published'",
    partition_key="tenant-1"  # Single-partition search for efficiency
)

# Vector search with custom distance metrics
results = await docs.vector_search(
    vector=query_vector,
    k=15,
    distance_function="cosine",  # or "euclidean", "dotproduct"
    include_embeddings=True  # Include vectors in results
)
```

### Multi-Vector Search

Search across multiple vector fields:

```python
@container(
    name="multi_vector_docs",
    vector_policy=[
        {
            "path": "/title_vector", 
            "dataType": "float32", 
            "dimensions": 768
        },
        {
            "path": "/content_vector", 
            "dataType": "float32", 
            "dimensions": 1536
        }
    ],
    vector_indexes=[
        {"path": "/title_vector", "type": "flat"},
        {"path": "/content_vector", "type": "quantizedFlat"}
    ]
)
class MultiVectorDocument(Document):
    id: str
    tenantId: PK[str]
    title: str
    content: str
    title_vector: List[float] | None = None
    content_vector: List[float] | None = None

# Search across both vectors
title_vector = await get_title_embedding(query_text)
content_vector = await get_content_embedding(query_text)

# Combined vector search
results = await docs.multi_vector_search([
    {"field": "title_vector", "vector": title_vector, "weight": 0.3},
    {"field": "content_vector", "vector": content_vector, "weight": 0.7}
], k=10)
```

## Full-Text Search

### Index Configuration

Configure full-text indexes on text fields:

```python
@container(
    name="searchable_content",
    full_text_indexes=[
        {
            "paths": ["/title", "/content", "/tags"]
        }
    ]
)
class TextSearchDocument(Document):
    id: str
    tenantId: PK[str]
    title: str
    content: str
    tags: List[str]
    author: str
```

### Basic Full-Text Search

Perform BM25-based text search:

```python
# Basic full-text search
search_results = await docs.full_text_search(
    query="machine learning python",
    k=15
)

for doc in search_results:
    print(f"Title: {doc.title}")
    print(f"Relevance Score: {doc._search_score}")
    print(f"Matched content: {doc.content[:200]}...")
```

### Advanced Full-Text Search

```python
# Full-text search with filtering and boosting
advanced_results = await docs.full_text_search(
    query="artificial intelligence",
    k=20,
    where_clause="c.author = 'expert_author' AND c.published_date > '2024-01-01'",
    boost_fields={
        "title": 2.0,      # Boost title matches
        "content": 1.0,    # Normal content weight
        "tags": 1.5        # Boost tag matches
    }
)

# Full-text search with phrase matching
phrase_results = await docs.full_text_search(
    query='"machine learning algorithms"',  # Exact phrase
    k=10,
    match_type="phrase"
)

# Full-text search with wildcards
wildcard_results = await docs.full_text_search(
    query="neural* AND network*",  # Wildcard matching
    k=10,
    match_type="wildcard"
)
```

### Multi-Field Text Search

Search across specific fields with different weights:

```python
# Weighted multi-field search
weighted_results = await docs.full_text_search(
    query="python programming",
    fields=[
        {"field": "title", "weight": 3.0},
        {"field": "content", "weight": 1.0},
        {"field": "tags", "weight": 2.0}
    ],
    k=15
)
```

## Hybrid Search (RRF)

### Combined Vector and Text Search

Hybrid search combines vector similarity and text relevance using Reciprocal Rank Fusion:

```python
# Hybrid search combining vector and text
query_text = "machine learning neural networks"
query_vector = await get_embedding(query_text)

hybrid_results = await docs.hybrid_search(
    text_query=query_text,
    vector=query_vector,
    k=15,
    alpha=0.6  # Weight: 0.6 for vector, 0.4 for text
)

for doc in hybrid_results:
    print(f"Title: {doc.title}")
    print(f"Hybrid Score: {doc._hybrid_score}")
    print(f"Vector Score: {doc._vector_score}")
    print(f"Text Score: {doc._text_score}")
```

### Advanced Hybrid Search

```python
# Hybrid search with additional filtering
filtered_hybrid = await docs.hybrid_search(
    text_query="deep learning frameworks",
    vector=query_vector,
    k=20,
    alpha=0.7,
    where_clause="c.category IN ('ai', 'ml') AND c.difficulty_level <= 3",
    boost_recent=True,  # Boost recent documents
    date_field="published_date"
)

# Hybrid search with custom RRF parameters
custom_hybrid = await docs.hybrid_search(
    text_query=query_text,
    vector=query_vector,
    k=15,
    rrf_constant=60,  # RRF constant (default: 60)
    vector_weight=0.8,
    text_weight=0.2
)
```

## Search Result Processing

### Result Ranking and Scoring

```python
# Process search results with detailed scoring
def analyze_search_results(results):
    for i, doc in enumerate(results):
        print(f"Rank {i+1}: {doc.title}")
        
        # Vector search scores
        if hasattr(doc, '_similarity_score'):
            print(f"  Similarity: {doc._similarity_score:.3f}")
        
        # Full-text search scores  
        if hasattr(doc, '_search_score'):
            print(f"  Relevance: {doc._search_score:.3f}")
        
        # Hybrid search scores
        if hasattr(doc, '_hybrid_score'):
            print(f"  Hybrid: {doc._hybrid_score:.3f}")
            print(f"  Vector: {doc._vector_score:.3f}")
            print(f"  Text: {doc._text_score:.3f}")
```

### Search Result Filtering

```python
# Post-process search results
def filter_and_rank_results(results, min_score=0.5, max_results=10):
    # Filter by minimum score
    filtered = [
        doc for doc in results 
        if getattr(doc, '_similarity_score', 0) >= min_score
    ]
    
    # Sort by score (descending)
    filtered.sort(
        key=lambda x: getattr(x, '_similarity_score', 0), 
        reverse=True
    )
    
    # Return top results
    return filtered[:max_results]
```

## Search Performance Optimization

### Index Optimization

```python
# Optimize vector indexes for different use cases
@container(
    name="optimized_search",
    vector_policy=[{
        "path": "/embedding",
        "dataType": "float32",
        "dimensions": 1536,
        "distanceFunction": "cosine"
    }],
    vector_indexes=[{
        "path": "/embedding",
        "type": "quantizedFlat",  # Better for large datasets
        "quantizationByteSize": 2,  # Compression level
        "rerankWithOriginalVectors": True  # Improve accuracy
    }]
)
class OptimizedDocument(Document):
    # ... document fields
    pass
```

### Search Query Optimization

```python
# Optimized search patterns
async def optimized_vector_search(query_vector, tenant_id):
    # Single-partition search for better performance
    return await docs.vector_search(
        vector=query_vector,
        k=50,
        partition_key=tenant_id,  # Efficient single-partition query
        similarity_score_threshold=0.6  # Pre-filter low scores
    )

async def optimized_hybrid_search(query_text, query_vector):
    # Balanced hybrid search with reasonable limits
    return await docs.hybrid_search(
        text_query=query_text,
        vector=query_vector,
        k=30,  # Reasonable result size
        alpha=0.6,  # Balanced weighting
        include_embeddings=False  # Reduce payload size
    )
```

## Real-World Search Applications

### Semantic Document Search

```python
async def semantic_document_search(user_query: str, user_context: dict):
    """Intelligent document search with context"""
    
    # Generate embedding for user query
    query_vector = await generate_embedding(user_query)
    
    # Build context-aware filter
    where_conditions = []
    if user_context.get("department"):
        where_conditions.append(f"c.department = '{user_context['department']}'")
    if user_context.get("access_level"):
        where_conditions.append(f"c.access_level <= {user_context['access_level']}")
    
    where_clause = " AND ".join(where_conditions) if where_conditions else None
    
    # Perform hybrid search
    results = await docs.hybrid_search(
        text_query=user_query,
        vector=query_vector,
        k=20,
        alpha=0.7,  # Favor semantic similarity
        where_clause=where_clause
    )
    
    # Post-process results
    return [
        {
            "document": doc,
            "relevance": doc._hybrid_score,
            "snippet": extract_snippet(doc.content, user_query)
        }
        for doc in results
    ]
```

### Content Recommendation System

```python
async def recommend_content(user_id: str, interaction_history: List[str]):
    """Recommend content based on user interaction history"""
    
    # Get user's interaction vectors
    user_vectors = []
    for doc_id in interaction_history[-10:]:  # Recent interactions
        doc = await docs.get(id=doc_id)
        if doc and doc.content_vector:
            user_vectors.append(doc.content_vector)
    
    if not user_vectors:
        return []
    
    # Create user profile vector (average of interactions)
    user_profile = np.mean(user_vectors, axis=0).tolist()
    
    # Find similar content
    recommendations = await docs.vector_search(
        vector=user_profile,
        k=15,
        where_clause="c.status = 'published' AND c.content_type = 'article'",
        similarity_score_threshold=0.6
    )
    
    # Filter out already seen content
    seen_ids = set(interaction_history)
    new_recommendations = [
        doc for doc in recommendations 
        if doc.id not in seen_ids
    ]
    
    return new_recommendations[:10]
```

### Multi-Modal Search

```python
async def multi_modal_search(
    text_query: str = None,
    image_vector: List[float] = None,
    audio_vector: List[float] = None,
    filters: dict = None
):
    """Search across multiple content modalities"""
    
    search_results = []
    
    # Text-based search
    if text_query:
        text_results = await docs.full_text_search(
            query=text_query,
            k=20
        )
        search_results.extend(text_results)
    
    # Image similarity search
    if image_vector:
        image_results = await docs.vector_search(
            vector=image_vector,
            k=15,
            where_clause="c.content_type = 'image'"
        )
        search_results.extend(image_results)
    
    # Audio similarity search
    if audio_vector:
        audio_results = await docs.vector_search(
            vector=audio_vector,
            k=15,
            where_clause="c.content_type = 'audio'"
        )
        search_results.extend(audio_results)
    
    # Deduplicate and rank
    unique_results = {doc.id: doc for doc in search_results}
    
    # Apply additional filters
    if filters:
        filtered_results = apply_filters(unique_results.values(), filters)
    else:
        filtered_results = unique_results.values()
    
    return list(filtered_results)[:20]
```

## Best Practices

### Vector Search Optimization

✅ **Best practices:**
- Use appropriate vector dimensions (768, 1536, etc.)
- Choose right distance function (cosine for normalized vectors)
- Set meaningful similarity thresholds
- Use single-partition searches when possible
- Consider quantized indexes for large datasets

❌ **Avoid:**
- Very high-dimensional vectors without quantization
- Cross-partition vector searches unnecessarily
- Very low similarity thresholds (noise)
- Including embeddings in results unless needed

### Full-Text Search Optimization

✅ **Best practices:**
- Index relevant text fields only
- Use field boosting strategically
- Implement query preprocessing (stemming, stop words)
- Set appropriate result limits
- Use phrase matching for exact requirements

❌ **Avoid:**
- Indexing all text fields unnecessarily
- Complex boolean queries without performance testing
- Very broad wildcard searches
- Ignoring query performance metrics

### Hybrid Search Strategy

✅ **Best practices:**
- Balance vector and text weights based on use case
- Use RRF for combining different ranking signals
- Test different alpha values for your data
- Monitor and tune performance regularly
- Consider user feedback for relevance tuning

## Related Documentation

- [Query Interface](query-interface.md) - Building complex search queries
- [Advanced CRUD Operations](advanced-crud.md) - Document operations
- [API Reference](api-reference.md) - Complete search method signatures
- [Bulk Operations](bulk-operations.md) - Batch processing search results