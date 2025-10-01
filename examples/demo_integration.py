"""Example script demonstrating ODM usage against local emulator.

This script shows real-world usage patterns:
1. Setting up models with search capabilities
2. Creating and managing documents  
3. Performing vector and full-text searches
4. Error handling and best practices

Prerequisites:
- Cosmos DB Local Emulator running
- Python environment with ODM installed
"""

import asyncio
from typing import List
from datetime import datetime

from cosmos_odm import Document, container, PK
from cosmos_odm.client import CosmosClientManager
from cosmos_odm.types import VectorPolicySpec, VectorIndexSpec, FullTextIndexSpec


# Local emulator connection
EMULATOR_ENDPOINT = "https://localhost:8081"
EMULATOR_KEY = "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="


@container(
    name="articles",
    partition_key_path="/category",
    vector_policy=[VectorPolicySpec(path="/content_embedding", data_type="float32", dimensions=384)],
    vector_indexes=[VectorIndexSpec(path="/content_embedding", type="flat")],
    full_text_indexes=[FullTextIndexSpec(paths=["/title", "/content", "/tags"])]
)
class Article(Document):
    """Article with vector and full-text search capabilities."""
    category: PK[str]
    title: str
    content: str
    author: str
    content_embedding: List[float]
    tags: List[str] = []
    view_count: int = 0
    published: bool = True


async def generate_mock_embedding(text: str) -> List[float]:
    """Generate mock embedding for demonstration.
    
    In real usage, you would use an embedding model like:
    - OpenAI embeddings
    - Azure OpenAI
    - Sentence Transformers
    - Cohere embeddings
    """
    # Simple hash-based mock embedding (384 dimensions)
    import hashlib
    hash_obj = hashlib.md5(text.encode())
    hash_int = int(hash_obj.hexdigest(), 16)
    
    # Generate 384 float values from hash
    embedding = []
    for i in range(384):
        # Create pseudo-random float between -1 and 1
        value = ((hash_int + i) % 10000) / 5000.0 - 1.0
        embedding.append(value)
    
    return embedding


async def main():
    """Main demonstration function."""
    print("🚀 Starting Cosmos ODM Integration Demo")
    print(f"📡 Connecting to emulator at {EMULATOR_ENDPOINT}")
    
    # Initialize client manager
    client_manager = CosmosClientManager(
        endpoint=EMULATOR_ENDPOINT,
        key=EMULATOR_KEY
    )
    
    try:
        # Create collection
        collection = await Article.bind("DemoDatabase", client_manager=client_manager)
        print("✅ Connected to Cosmos DB and created collection")
        
        # Sample articles data
        articles_data = [
            {
                "category": "technology",
                "title": "Introduction to Machine Learning",
                "content": "Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed. It involves algorithms that can identify patterns in data and make predictions or decisions.",
                "author": "Alice Johnson",
                "tags": ["AI", "ML", "technology", "data science"]
            },
            {
                "category": "technology", 
                "title": "Vector Databases Explained",
                "content": "Vector databases are specialized databases designed to store and query high-dimensional vectors efficiently. They are essential for similarity search, recommendation systems, and AI applications.",
                "author": "Bob Smith",
                "tags": ["database", "vectors", "search", "AI"]
            },
            {
                "category": "science",
                "title": "Climate Change and Technology",
                "content": "Technology plays a crucial role in addressing climate change. From renewable energy to carbon capture, innovative solutions are being developed to combat global warming.",
                "author": "Carol Wilson",
                "tags": ["climate", "environment", "sustainability", "green tech"]
            },
            {
                "category": "health",
                "title": "AI in Healthcare",
                "content": "Artificial intelligence is revolutionizing healthcare by improving diagnosis accuracy, drug discovery, and personalized treatment plans. AI systems can analyze medical images and predict health outcomes.",
                "author": "David Chen",
                "tags": ["healthcare", "AI", "medicine", "diagnosis"]
            }
        ]
        
        # Create and insert articles
        print("\n📝 Creating articles with embeddings...")
        created_articles = []
        
        for article_data in articles_data:
            # Generate embedding for the content
            embedding = await generate_mock_embedding(article_data["content"])
            
            # Create article
            article = Article(
                category=PK(article_data["category"]),
                title=article_data["title"],
                content=article_data["content"],
                author=article_data["author"],
                content_embedding=embedding,
                tags=article_data["tags"]
            )
            
            # Insert into database
            created = await collection.create(article)
            created_articles.append(created)
            print(f"  ✅ Created: {created.title}")
        
        print(f"\n🎉 Created {len(created_articles)} articles successfully")
        
        # Demonstrate CRUD operations
        print("\n🔍 Testing CRUD Operations...")
        
        # Get specific article
        first_article = created_articles[0]
        retrieved = await collection.get(first_article.id, first_article.category)
        print(f"  📖 Retrieved: {retrieved.title}")
        
        # Update article
        retrieved.view_count = 100
        updated = await collection.replace(retrieved)
        print(f"  ✏️  Updated view count: {updated.view_count}")
        
        # Demonstrate querying
        print("\n🔍 Testing Query Operations...")
        
        # Simple query
        tech_articles = []
        async for page in collection.query(
            "SELECT * FROM c WHERE c.category = 'technology'",
            max_item_count=10
        ):
            tech_articles.extend(page.items)
            print(f"  📊 Query page RU cost: {page.ru_metrics.request_charge:.2f}")
        
        print(f"  📚 Found {len(tech_articles)} technology articles")
        
        # Query with filters
        filter_results = []
        async for page in collection.query(
            "SELECT * FROM c",
            filter={"category": "technology", "view_count": {"$gt": 50}},
            max_item_count=5
        ):
            filter_results.extend(page.items)
        
        print(f"  🔎 Found {len(filter_results)} articles with view_count > 50")
        
        # Demonstrate search operations (if supported by emulator)
        print("\n🔍 Testing Search Operations...")
        
        try:
            # Vector search
            query_embedding = await generate_mock_embedding("artificial intelligence machine learning")
            
            vector_results = await collection.vector_search(
                vector_field="content_embedding",
                query_vector=query_embedding,
                limit=3,
                filter={"published": True}
            )
            
            print(f"  🎯 Vector search found {len(vector_results.items)} similar articles:")
            for i, article in enumerate(vector_results.items):
                score = vector_results.scores[i] if vector_results.scores else "N/A"
                print(f"    {i+1}. {article.title} (score: {score})")
                
        except Exception as e:
            print(f"  ⚠️  Vector search not available in emulator: {e}")
        
        try:
            # Full-text search
            text_results = await collection.full_text_search(
                text_fields=["title", "content"],
                query_text="machine learning artificial intelligence",
                limit=3
            )
            
            print(f"  📝 Full-text search found {len(text_results.items)} relevant articles:")
            for i, article in enumerate(text_results.items):
                score = text_results.scores[i] if text_results.scores else "N/A"
                print(f"    {i+1}. {article.title} (score: {score})")
                
        except Exception as e:
            print(f"  ⚠️  Full-text search not available in emulator: {e}")
        
        try:
            # Hybrid search
            hybrid_results = await collection.hybrid_search(
                vector_fields=[("content_embedding", query_embedding)],
                text_fields=[("content", "technology innovation")],
                limit=2
            )
            
            print(f"  🚀 Hybrid search found {len(hybrid_results.items)} articles:")
            for article in hybrid_results.items:
                print(f"    • {article.title}")
                
        except Exception as e:
            print(f"  ⚠️  Hybrid search not available in emulator: {e}")
        
        # Demonstrate error handling
        print("\n🛡️  Testing Error Handling...")
        
        try:
            # Try to get non-existent document
            await collection.get("nonexistent", PK("nonexistent"))
        except Exception as e:
            print(f"  ✅ Correctly caught error: {type(e).__name__}")
        
        # Cleanup - delete test articles
        print("\n🧹 Cleaning up test data...")
        for article in created_articles:
            await collection.delete(article.id, article.category)
        print("  ✅ Deleted all test articles")
        
        print("\n🎉 Demo completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Close client connections
        await client_manager.close()
        print("🔌 Closed database connections")


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())