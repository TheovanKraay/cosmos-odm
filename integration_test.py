#!/usr/bin/env python3
"""Integration tests for Cosmos ODM - simplified asyncio version."""

import asyncio
import sys
from typing import List

from cosmos_odm import Collection, PK, CosmosClientManager
from cosmos_odm.errors import NotFound
from cosmos_odm.model import Document, container
from pydantic import Field


# Test models
@container("Products", "/pk")
class Product(Document):
    category_id: PK[str] = Field(alias="pk")
    name: str
    description: str
    price: float
    embedding: List[float] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


@container("Users", "/pk")
class User(Document):
    user_id: PK[str] = Field(alias="pk")
    email: str
    name: str
    age: int


async def test_crud_operations():
    """Test basic CRUD operations."""
    print("Testing CRUD operations...")
    
    # Initialize client manager with explicit emulator settings
    client_manager = CosmosClientManager(
        endpoint="https://localhost:8081",
        key="C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==",
        connection_verify=False  # Disable SSL verification for emulator
    )
    collection = Collection[Product](
        document_type=Product,
        database_name="TestODM",
        client_manager=client_manager
    )
    
    try:
        # Test create
        product = Product(
            category_id=PK("electronics"),
            name="Laptop",
            description="High-performance laptop for developers",
            price=1299.99,
            embedding=[0.1, 0.2, 0.3],
            tags=["computer", "laptop", "electronics"]
        )
        
        created = await collection.create(product)
        print(f"✓ Created product: {created.name} (ID: {created.id})")
        
        # Test get
        retrieved = await collection.get(created.category_id, created.id)
        assert retrieved.name == "Laptop"
        assert retrieved.price == 1299.99
        print(f"✓ Retrieved product: {retrieved.name}")
        
        # Test replace
        retrieved.price = 1199.99
        replaced = await collection.replace(retrieved)
        assert replaced.price == 1199.99
        print(f"✓ Updated product price to: ${replaced.price}")
        
        # Test delete
        await collection.delete(replaced)
        print("✓ Deleted product")
        
        # Test not found
        try:
            await collection.get(created.category_id, created.id)
            assert False, "Should have raised NotFound"
        except NotFound:
            print("✓ NotFound exception raised correctly")
            
    finally:
        await client_manager.close()
        
    print("✅ CRUD operations test passed!\n")


async def test_query_operations():
    """Test query operations."""
    print("Testing query operations...")
    
    client_manager = CosmosClientManager(
        endpoint="https://localhost:8081",
        key="C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==",
        connection_verify=False
    )
    collection = Collection[Product](
        document_type=Product,
        database_name="TestODM",
        client_manager=client_manager
    )
    
    try:
        # Create test data
        products = [
            Product(
                category_id=PK("tech"),
                name="Smartphone",
                description="Latest smartphone with AI features",
                price=899.99,
                embedding=[0.1, 0.8, 0.2],
                tags=["phone", "mobile", "ai"]
            ),
            Product(
                category_id=PK("tech"), 
                name="Tablet",
                description="Portable tablet for work and entertainment",
                price=599.99,
                embedding=[0.2, 0.7, 0.3],
                tags=["tablet", "portable"]
            ),
            Product(
                category_id=PK("books"),
                name="AI Handbook",
                description="Comprehensive guide to artificial intelligence",
                price=49.99,
                embedding=[0.3, 0.6, 0.4],
                tags=["book", "ai", "guide"]
            )
        ]
        
        created_products = []
        for product in products:
            created = await collection.create(product)
            created_products.append(created)
            
        print(f"✓ Created {len(created_products)} test products")
        
        # Test simple query
        query = "SELECT * FROM c WHERE c.category_id = 'tech'"
        results = []
        async for page in collection.query(query):
            results.extend(page.items)
            
        tech_products = [p for p in results if p.category_id.value == "tech"]
        assert len(tech_products) >= 2
        print(f"✓ Found {len(tech_products)} tech products")
        
        # Test parameterized query
        query = "SELECT * FROM c WHERE c.price < @max_price"
        parameters = {"max_price": 100}
        
        results = []
        async for page in collection.query(query, parameters=parameters):
            results.extend(page.items)
            
        cheap_products = [p for p in results if p.price < 100]
        assert len(cheap_products) >= 1
        print(f"✓ Found {len(cheap_products)} products under $100")
        
        # Cleanup
        for product in created_products:
            try:
                await collection.delete(product)
            except NotFound:
                pass  # Already deleted
                
    finally:
        await client_manager.close()
        
    print("✅ Query operations test passed!\n")


async def test_ru_metrics():
    """Test RU metrics tracking."""
    print("Testing RU metrics...")
    
    client_manager = CosmosClientManager(
        endpoint="https://localhost:8081",
        key="C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==",
        connection_verify=False
    )
    collection = Collection[Product](
        document_type=Product,
        database_name="TestODM",
        client_manager=client_manager
    )
    
    try:
        product = Product(
            category_id=PK("ru_test"),
            name="RU Test Product",
            description="Testing RU tracking",
            price=100.0,
            embedding=[0.1, 0.2, 0.3]
        )
        
        # Create and verify RU tracking
        created = await collection.create(product)
        assert hasattr(created, '_ru_charge')
        assert created._ru_charge > 0
        print(f"✓ Create operation consumed {created._ru_charge} RUs")
        
        # Get and verify RU tracking
        retrieved = await collection.get(created.category_id, created.id)
        assert hasattr(retrieved, '_ru_charge')
        assert retrieved._ru_charge > 0
        print(f"✓ Get operation consumed {retrieved._ru_charge} RUs")
        
        # Cleanup
        await collection.delete(retrieved)
        
    finally:
        await client_manager.close()
        
    print("✅ RU metrics test passed!\n")


async def main():
    """Run all integration tests."""
    print("🚀 Starting Cosmos ODM Integration Tests")
    print("=" * 50)
    
    try:
        await test_crud_operations()
        await test_query_operations()
        await test_ru_metrics()
        
        print("🎉 All integration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)