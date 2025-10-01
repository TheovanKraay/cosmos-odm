#!/usr/bin/env python3
"""Simple integration test for Cosmos ODM."""

import asyncio
import logging
import sys
from typing import List

from cosmos_odm import Collection, PK, CosmosClientManager
from cosmos_odm.model import Document, container
from pydantic import Field

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test model
@container("Products", "/pk")
class Product(Document):
    category_id: PK[str] = Field(alias="pk")
    name: str
    price: float


async def setup_database():
    """Setup database and container for testing."""
    logger.info("Setting up database and container...")
    
    # Use explicit emulator settings
    client_manager = CosmosClientManager(
        endpoint="https://localhost:8081",
        key="C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==",
        connection_verify=False  # Disable SSL verification for emulator
    )
    
    try:
        # Try to create the database
        await client_manager.async_client.create_database_if_not_exists("TestODM")
        logger.info("Database 'TestODM' created or already exists")
        
        # Get the database
        database = client_manager.async_client.get_database_client("TestODM")
        
        # Create container for Products
        partition_key_def = {"paths": ["/pk"], "kind": "Hash"}
        
        await database.create_container_if_not_exists(
            id="Products",
            partition_key=partition_key_def,
            offer_throughput=400
        )
        logger.info("Container 'Products' created or already exists")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to setup database: {e}")
        return False
    finally:
        # Close the client
        await client_manager.async_client.close()


async def test_basic_operations():
    """Test basic operations."""
    logger.info("Testing basic operations...")
    
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
    
    # Test create
    product = Product(
        category_id=PK("electronics"),
        name="Test Product",
        price=99.99
    )
    
    try:
        created = await collection.create(product)
        logger.info(f"✅ Created product: {created.id}")
        
        # Test read
        read_product = await collection.get("electronics", created.id)
        logger.info(f"✅ Read product: {read_product.name}")
        
        # Test update (replace)
        read_product.price = 79.99
        updated = await collection.replace(read_product)
        logger.info(f"✅ Updated product price: {updated.price}")
        
        # Test delete
        await collection.delete("electronics", updated.id)
        logger.info("✅ Deleted product")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False
    finally:
        # Close the client
        await client_manager.async_client.close()


async def main():
    """Main test function."""
    logger.info("🚀 Starting Simple Cosmos ODM Test")
    logger.info("=" * 50)
    
    # Setup database
    if not await setup_database():
        logger.error("Failed to setup database, exiting")
        return False
    
    # Run tests
    success = await test_basic_operations()
    
    if success:
        logger.info("🎉 All tests passed!")
    else:
        logger.error("❌ Tests failed!")
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)