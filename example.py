"""Example usage of Cosmos ODM with native search capabilities."""

import asyncio
from typing import List
from datetime import datetime
from pydantic import Field

from cosmos_odm import Document, container, PK, ETag, CosmosClientManager


@container(
    name="documents",
    partition_key_path="/tenantId", 
    ttl=30*24*3600,  # 30 days
    vector_policy=[{
        "path": "/content_vector",
        "dataType": "float32",
        "dimensions": 4,  # Small for demo
        "distanceFunction": "cosine"
    }],
    vector_indexes=[{
        "path": "/content_vector",
        "type": "flat"
    }],
    full_text_indexes=[{
        "paths": ["/title", "/content"]
    }]
)
class BlogPost(Document):
    """Example blog post document."""
    
    id: str
    tenantId: PK[str] = Field(serialization_alias="tenantId")
    title: str
    content: str
    content_vector: List[float] = []
    author: str
    status: str = "draft"
    tags: List[str] = []
    view_count: int = 0
    etag: ETag | None = None


def generate_mock_vector(seed: int) -> List[float]:
    """Generate a mock vector for demonstration."""
    import random
    random.seed(seed)
    return [random.uniform(-1, 1) for _ in range(4)]


async def demo_crud_operations(docs):
    """Demonstrate basic CRUD operations."""
    print("=== CRUD Operations Demo ===")
    
    # Create documents
    post1 = BlogPost(
        id="post-1",
        tenantId=PK("blog-tenant"),
        title="Introduction to Vector Search",
        content="Vector search enables semantic similarity matching using embeddings...",
        content_vector=generate_mock_vector(1),
        author="Alice",
        status="published",
        tags=["vector-search", "ai", "embeddings"]
    )
    
    post2 = BlogPost(
        id="post-2", 
        tenantId=PK("blog-tenant"),
        title="Full-Text Search with BM25",
        content="BM25 is a ranking function used for full-text search relevance scoring...",
        content_vector=generate_mock_vector(2),
        author="Bob",
        status="published", 
        tags=["full-text", "search", "bm25"]
    )
    
    try:
        # Create documents
        created1 = await docs.create(post1)
        created2 = await docs.create(post2)
        print(f"✓ Created {created1.title}")
        print(f"✓ Created {created2.title}")
        
        # Point read (most efficient)
        retrieved = await docs.get(pk="blog-tenant", id="post-1")
        print(f"✓ Retrieved: {retrieved.title}")
        
        # Update with optimistic concurrency
        retrieved.view_count += 1
        updated = await docs.replace(retrieved, if_match=retrieved.etag.value)
        print(f"✓ Updated view count: {updated.view_count}")
        
        return [created1, created2]
        
    except Exception as e:
        print(f"✗ CRUD error: {e}")
        return []


async def demo_query_operations(docs):
    """Demonstrate query operations with pagination."""
    print("\n=== Query Operations Demo ===")
    
    try:
        # Simple query
        page_count = 0
        total_items = 0
        total_ru = 0
        
        async for page in docs.query(
            sql="SELECT * FROM c WHERE c.status = @status",
            parameters={"status": "published"},
            partition_key="blog-tenant",
            max_item_count=10
        ):
            page_count += 1
            total_items += len(page.items)
            total_ru += page.ru_metrics.request_charge
            
            print(f"✓ Page {page_count}: {len(page.items)} items, {page.ru_metrics.request_charge:.2f} RU")
            
            for item in page.items:
                print(f"  - {item.title} by {item.author}")
        
        print(f"✓ Total: {total_items} items across {page_count} pages, {total_ru:.2f} RU")
        
    except Exception as e:
        print(f"✗ Query error: {e}")


async def demo_vector_search(docs):
    """Demonstrate vector similarity search."""
    print("\n=== Vector Search Demo ===")
    
    try:
        # Search for documents similar to a query vector
        query_vector = generate_mock_vector(10)  # Mock query embedding
        
        results = await docs.vector_search(
            vector=query_vector,
            vector_path="/content_vector",
            k=5,
            filter={"status": "published"},
            partition_key="blog-tenant"
        )
        
        print(f"✓ Vector search completed: {len(results.items)} results")
        print(f"✓ Search cost: {results.ru_metrics.request_charge:.2f} RU")
        
        for i, doc in enumerate(results.items):
            score = results.scores[i] if results.scores else "N/A"
            print(f"  {i+1}. {doc.title} (Score: {score})")
        
    except Exception as e:
        print(f"✗ Vector search error: {e}")


async def demo_full_text_search(docs):
    """Demonstrate full-text search."""
    print("\n=== Full-Text Search Demo ===")
    
    try:
        # Search using keywords
        results = await docs.full_text_search(
            text="vector search similarity",
            fields=["/title", "/content"],
            k=5,
            filter={"status": "published"},
            partition_key="blog-tenant"
        )
        
        print(f"✓ Full-text search completed: {len(results.items)} results")
        print(f"✓ Search cost: {results.ru_metrics.request_charge:.2f} RU")
        
        for i, doc in enumerate(results.items):
            score = results.scores[i] if results.scores else "N/A"
            print(f"  {i+1}. {doc.title} (Score: {score})")
        
    except Exception as e:
        print(f"✗ Full-text search error: {e}")


async def demo_hybrid_search(docs):
    """Demonstrate hybrid search with RRF."""
    print("\n=== Hybrid Search Demo ===")
    
    try:
        # Combine vector and text search
        query_vector = generate_mock_vector(15)
        
        results = await docs.hybrid_search(
            text="search algorithms",
            vector=query_vector,
            fields=["/title", "/content"],
            vector_path="/content_vector",
            k=5,
            weights=[2, 1],  # Favor text over vector
            filter={"status": "published"},
            partition_key="blog-tenant"
        )
        
        print(f"✓ Hybrid search completed: {len(results.items)} results")
        print(f"✓ Search cost: {results.ru_metrics.request_charge:.2f} RU")
        
        for i, doc in enumerate(results.items):
            score = results.scores[i] if results.scores else "N/A"
            print(f"  {i+1}. {doc.title} (RRF Score: {score})")
        
    except Exception as e:
        print(f"✗ Hybrid search error: {e}")


async def demo_index_management(docs):
    """Demonstrate index provisioning."""
    print("\n=== Index Management Demo ===")
    
    try:
        # Ensure all required indexes are provisioned
        indexing_policy = await docs.ensure_indexes()
        
        print("✓ Index provisioning completed")
        print("✓ Vector policy configured:", "vectorEmbeddingPolicy" in indexing_policy)
        print("✓ Vector indexes configured:", len(indexing_policy.get("vectorIndexes", [])))
        print("✓ Full-text indexes configured:", len(indexing_policy.get("fullTextIndexes", [])))
        
    except Exception as e:
        print(f"✗ Index management error: {e}")


async def cleanup_demo_data(docs):
    """Clean up demo data."""
    print("\n=== Cleanup ===")
    
    try:
        await docs.delete(pk="blog-tenant", id="post-1")
        await docs.delete(pk="blog-tenant", id="post-2")
        print("✓ Demo data cleaned up")
        
    except Exception as e:
        print(f"Note: Cleanup error (data may not exist): {e}")


async def main():
    """Run the complete demo."""
    print("Cosmos ODM Demo")
    print("===============")
    
    # Note: You'll need to set these environment variables or update the connection
    client_manager = CosmosClientManager(
        # connection_string="AccountEndpoint=https://your-account.documents.azure.com:443/;AccountKey=your-key==;"
        # For demo purposes, we'll just show the interface
    )
    
    try:
        # Bind to collection
        docs = await BlogPost.bind(
            database="demo_db",
            client_manager=client_manager
        )
        
        print("✓ Connected to Cosmos DB")
        
        # Run demos (commented out for scaffolding - would need real Cosmos DB)
        # await demo_index_management(docs)
        # await demo_crud_operations(docs)
        # await demo_query_operations(docs)
        # await demo_vector_search(docs)
        # await demo_full_text_search(docs)
        # await demo_hybrid_search(docs)
        # await cleanup_demo_data(docs)
        
        print("\nDemo completed successfully!")
        print("\nTo run this demo with real data:")
        print("1. Set up Azure Cosmos DB account with vector/full-text search enabled")
        print("2. Update connection string in main()")
        print("3. Uncomment the demo function calls")
        
    except Exception as e:
        print(f"Demo error: {e}")
        print("\nThis is expected when running without real Cosmos DB credentials.")
    
    finally:
        await client_manager.close()


if __name__ == "__main__":
    asyncio.run(main())