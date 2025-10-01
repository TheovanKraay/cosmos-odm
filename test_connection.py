#!/usr/bin/env python3
"""Simple connection test to verify emulator is working."""

import asyncio
import sys
from azure.cosmos.aio import CosmosClient
from azure.cosmos import exceptions


async def test_emulator_connection():
    """Test basic connection to Cosmos DB emulator."""
    # Emulator connection settings
    url = "https://localhost:8081"
    key = "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
    
    try:
        # Create client with SSL verification disabled for emulator
        async with CosmosClient(url, key, connection_verify=False) as client:
            print("✓ Successfully created Cosmos client")
            
            # Try to list databases
            try:
                databases = []
                async for db in client.list_databases():
                    databases.append(db)
                print(f"✓ Successfully listed databases: {len(databases)} found")
                
                # Try to create a test database
                try:
                    db_name = "ConnectionTest"
                    database = await client.create_database_if_not_exists(db_name)
                    print(f"✓ Successfully created/accessed database: {db_name}")
                    
                        # Try to create a test container
                        try:
                            from azure.cosmos import PartitionKey
                            container_name = "TestContainer"
                            container = await database.create_container_if_not_exists(
                                id=container_name,
                                partition_key=PartitionKey(path="/id")
                            )
                            print(f"✓ Successfully created/accessed container: {container_name}")                        # Try a simple document operation
                        try:
                            test_doc = {
                                "id": "test-doc-1",
                                "message": "Hello from ODM test!"
                            }
                            await container.create_item(test_doc)
                            print("✓ Successfully created test document")
                            
                            # Try to read it back
                            retrieved = await container.read_item("test-doc-1", "test-doc-1")
                            print(f"✓ Successfully retrieved document: {retrieved['message']}")
                            
                        except Exception as e:
                            print(f"✗ Document operation failed: {e}")
                            return False
                            
                    except Exception as e:
                        print(f"✗ Container creation failed: {e}")
                        return False
                        
                except Exception as e:
                    print(f"✗ Database creation failed: {e}")
                    return False
                    
            except Exception as e:
                print(f"✗ Database listing failed: {e}")
                return False
                
    except Exception as e:
        print(f"✗ Client creation failed: {e}")
        print("Make sure the Cosmos DB emulator is running on https://localhost:8081")
        return False
    
    print("🎉 All connection tests passed!")
    return True


if __name__ == "__main__":
    result = asyncio.run(test_emulator_connection())
    sys.exit(0 if result else 1)