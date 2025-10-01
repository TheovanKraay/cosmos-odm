"""
Comprehensive Examples: Enhanced CRUD Operations, State Management, and Query Interface

This example demonstrates all the high priority features implemented for Cosmos ODM:

1. Enhanced CRUD Operations (save, replace, sync)
2. Document State Management
3. Type-safe Query Interface  
4. Bulk Operations
5. Merge Strategies

Run this example to see how to use the enhanced features.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, List

from cosmos_odm import (
    Document, Collection, CosmosClientManager, 
    MergeStrategy, FindQuery, BulkWriter, PK
)


# Define your document models
class User(Document):
    """User document with enhanced features."""
    
    name: str
    email: str
    age: int
    active: bool = True
    tags: List[str] = []
    last_login: Optional[datetime] = None
    
    class Config:
        container_name = "users"
        partition_key = "pk" 


class BlogPost(Document):
    """Blog post document."""
    
    title: str
    content: str
    author_id: str
    published: bool = False
    tags: List[str] = []
    view_count: int = 0
    
    class Config:
        container_name = "blog_posts"
        partition_key = "pk"


async def example_enhanced_crud():
    """Demonstrate enhanced CRUD operations."""
    
    print("=== Enhanced CRUD Operations ===")
    
    # Setup
    client_manager = CosmosClientManager(
        connection_string="your_connection_string",
        database_name="blog_db"
    )
    users_collection = Collection(User, "blog_db", client_manager)
    
    # 1. Create and Save Document
    user = User(
        id="user1",
        pk="users",
        name="John Doe",
        email="john@example.com", 
        age=30,
        tags=["developer", "python"]
    )
    
    # Enable state management for change tracking
    user._enable_state_management()
    
    # Save (upsert) the document
    saved_user = await users_collection.save(user)
    print(f"✓ Saved user: {saved_user.name}")
    
    # 2. Make changes and save only changed fields
    saved_user.age = 31
    saved_user.last_login = datetime.now(timezone.utc)
    saved_user.tags.append("senior")
    
    print(f"Changed fields: {saved_user.get_changes()}")
    
    # Save only the changes (more efficient)
    updated_user = await users_collection.save_changes(saved_user)
    if updated_user:
        print(f"✓ Updated user with changes only")
    
    # 3. Replace entire document
    user.active = False
    replaced_user = await users_collection.replace_document(user)
    print(f"✓ Replaced user document")
    
    # 4. Sync document with database version
    # Useful when you want to merge local changes with remote changes
    synced_user = await users_collection.sync_document(
        user, 
        merge_strategy=MergeStrategy.REMOTE  # Use remote version
    )
    print(f"✓ Synced user with database version")


async def example_state_management():
    """Demonstrate document state management."""
    
    print("\n=== Document State Management ===")
    
    # Create document
    user = User(
        id="user2",
        pk="users",
        name="Jane Smith",
        email="jane@example.com",
        age=28
    )
    
    # Enable state management
    user._enable_state_management()
    print(f"State management enabled: {user._state_management_enabled}")
    
    # Save initial state
    user._save_state()
    print(f"Document changed: {user.is_changed}")  # False
    
    # Make changes
    user.name = "Jane Wilson"  # Changed last name
    user.age = 29
    user.tags = ["designer", "ui/ux"]
    
    print(f"Document changed: {user.is_changed}")  # True
    
    # Get specific changes
    changes = user.get_changes()
    print(f"Changed fields: {changes}")
    
    # Rollback changes
    print("\nRolling back changes...")
    user.rollback()
    print(f"Name after rollback: {user.name}")  # Back to "Jane Smith"
    print(f"Age after rollback: {user.age}")    # Back to 28
    print(f"Document changed: {user.is_changed}")  # False
    
    # Test merge strategies
    print(f"Available merge strategies: {[s.value for s in MergeStrategy]}")


async def example_query_interface():
    """Demonstrate the type-safe query interface."""
    
    print("\n=== Type-Safe Query Interface ===")
    
    client_manager = CosmosClientManager(
        connection_string="your_connection_string",
        database_name="blog_db"
    )
    users_collection = Collection(User, "blog_db", client_manager)
    posts_collection = Collection(BlogPost, "blog_db", client_manager)
    
    # 1. Basic queries
    print("Building queries...")
    
    # Find active users
    active_users_query = users_collection.find("c.active = @active", active=True)
    print("✓ Created query for active users")
    
    # Find users by age range with ordering
    young_users_query = (users_collection
                        .find("c.age >= @min AND c.age <= @max", min=18, max=35)
                        .order_by("age")
                        .limit(10))
    print("✓ Created query for young users with ordering and limit")
    
    # 2. Complex queries with chaining
    senior_devs_query = (users_collection
                        .find("c.active = @active", active=True)
                        .where("ARRAY_CONTAINS(c.tags, @tag)", tag="senior")
                        .order_by("name")
                        .skip(0)
                        .limit(20))
    
    print("✓ Created complex query for senior developers")
    
    # 3. Execute queries (commented out - requires real connection)
    """
    # Get all results as list
    active_users = await active_users_query.to_list()
    print(f"Found {len(active_users)} active users")
    
    # Get first result
    first_young_user = await young_users_query.first()
    if first_young_user:
        print(f"Youngest user: {first_young_user.name}")
    
    # Count results
    senior_dev_count = await senior_devs_query.count()
    print(f"Number of senior developers: {senior_dev_count}")
    
    # Check if any exist
    has_senior_devs = await senior_devs_query.exists()
    print(f"Has senior developers: {has_senior_devs}")
    """
    
    # 4. Convenience methods
    print("\\nUsing convenience methods...")
    
    # Find one user by email
    # user = await users_collection.find_one("c.email = @email", email="john@example.com")
    
    # Find all users (no conditions)
    all_users_query = users_collection.find_all()
    print("✓ Created query for all users")
    
    # Count all active users
    # active_count = await users_collection.count_documents("c.active = @active", active=True)
    
    # Check if any users exist with specific tag
    # has_python_devs = await users_collection.exists_documents("ARRAY_CONTAINS(c.tags, @tag)", tag="python")


async def example_bulk_operations():
    """Demonstrate bulk operations."""
    
    print("\n=== Bulk Operations ===")
    
    client_manager = CosmosClientManager(
        connection_string="your_connection_string",
        database_name="blog_db"
    )
    users_collection = Collection(User, "blog_db", client_manager)
    
    # 1. Create bulk writer
    bulk = users_collection.bulk_writer()
    print("✓ Created bulk writer")
    
    # 2. Add various operations
    
    # Insert new users
    new_users = [
        User(id=f"bulk_user_{i}", pk="users", name=f"User {i}", email=f"user{i}@example.com", age=20+i)
        for i in range(5)
    ]
    
    for user in new_users:
        bulk.insert(user)
    
    print(f"✓ Added {len(new_users)} insert operations")
    
    # Upsert existing user
    existing_user = User(
        id="existing_user",
        pk="users", 
        name="Updated User",
        email="updated@example.com",
        age=35
    )
    bulk.upsert(existing_user)
    print("✓ Added upsert operation")
    
    # Delete operation
    bulk.delete("users", "user_to_delete")
    print("✓ Added delete operation")
    
    # 3. Execute all operations (commented out - requires real connection)
    """
    results = await bulk.execute()
    
    successful_ops = [r for r in results if r["success"]]
    failed_ops = [r for r in results if not r["success"]]
    
    print(f"Successful operations: {len(successful_ops)}")
    print(f"Failed operations: {len(failed_ops)}")
    
    for failed_op in failed_ops:
        print(f"Failed {failed_op['operation']}: {failed_op['error']}")
    """
    
    # 4. Convenience bulk methods
    print("\\nUsing convenience bulk methods...")
    
    # Insert many documents at once
    more_users = [
        User(id=f"many_user_{i}", pk="users", name=f"Many User {i}", email=f"many{i}@example.com", age=25+i)
        for i in range(3)
    ]
    
    # inserted_users = await users_collection.insert_many(more_users)
    print(f"✓ Prepared to insert {len(more_users)} users")
    
    # Delete many documents by condition
    # deleted_count = await users_collection.delete_many("c.age < @max_age", max_age=25)
    print("✓ Prepared to delete users by age condition")


async def example_advanced_scenarios():
    """Demonstrate advanced usage scenarios."""
    
    print("\n=== Advanced Usage Scenarios ===")
    
    client_manager = CosmosClientManager(
        connection_string="your_connection_string", 
        database_name="blog_db"
    )
    users_collection = Collection(User, "blog_db", client_manager)
    
    # 1. Optimistic concurrency with ETags
    print("1. Optimistic Concurrency Control")
    
    user = User(
        id="concurrent_user",
        pk="users",
        name="Concurrent User",
        email="concurrent@example.com",
        age=30
    )
    
    # Save and get ETag
    # saved_user = await users_collection.save(user)
    # print(f"✓ Saved user with ETag: {saved_user.etag}")
    
    # Replace with ETag validation (will fail if document was modified)
    # replaced_user = await users_collection.replace_document(saved_user, ignore_etag=False)
    
    # Replace ignoring ETag (always succeeds)
    # replaced_user = await users_collection.replace_document(saved_user, ignore_etag=True)
    
    # 2. Conflict resolution with merge strategies
    print("\\n2. Conflict Resolution")
    
    # Simulate conflict scenario
    local_user = User(
        id="conflict_user",
        pk="users",
        name="Local Changes",
        email="local@example.com", 
        age=25
    )
    local_user._enable_state_management()
    local_user._save_state()
    
    # Make local changes
    local_user.age = 26
    local_user.tags = ["local_tag"]
    
    print(f"Local changes: {local_user.get_changes()}")
    
    # Different merge strategies for conflicts:
    
    # REMOTE: Use database version (discard local changes)
    # synced_remote = await users_collection.sync_document(local_user, MergeStrategy.REMOTE)
    
    # LOCAL: Keep local changes, apply to database version  
    # synced_local = await users_collection.sync_document(local_user, MergeStrategy.LOCAL)
    
    # MANUAL: Application handles merge logic
    # This would require custom implementation
    
    # 3. Efficient partial updates
    print("\\n3. Efficient Partial Updates")
    
    user_for_update = User(
        id="update_user",
        pk="users",
        name="Original Name",
        email="original@example.com",
        age=30
    )
    user_for_update._enable_state_management()
    user_for_update._save_state()
    
    # Only change specific fields
    user_for_update.age = 31
    user_for_update.last_login = datetime.now(timezone.utc)
    
    # Save only the changed fields (more efficient than full replace)
    # updated_user = await users_collection.save_changes(user_for_update)
    
    print("✓ Demonstrated partial update scenario")
    
    # 4. Complex query patterns
    print("\\n4. Complex Query Patterns")
    
    # Pagination with continuation tokens
    page_query = (users_collection
                 .find("c.active = @active", active=True)
                 .order_by("name")
                 .skip(0)
                 .limit(10))
    
    # Execute with pagination (would need real connection)
    """
    page_1 = await page_query.to_list()
    
    # Get next page
    next_page_query = (users_collection
                      .find("c.active = @active", active=True)
                      .order_by("name") 
                      .skip(10)
                      .limit(10))
    page_2 = await next_page_query.to_list()
    """
    
    # Conditional operations
    condition_query = (users_collection
                      .find("c.age >= @min_age", min_age=18)
                      .where("c.active = @active", active=True)
                      .where("ARRAY_LENGTH(c.tags) > @min_tags", min_tags=0))
    
    print("✓ Built complex conditional query")
    
    # Aggregation-style queries (using SQL)
    stats_query = users_collection.find("c.active = @active", active=True)
    
    # Count active users by age group (would need custom SQL)
    # This would be: SELECT c.age DIV 10 as age_group, COUNT(1) as count FROM c WHERE c.active = true GROUP BY c.age DIV 10
    
    print("✓ Demonstrated advanced query patterns")


async def main():
    """Run all examples."""
    
    print("Cosmos ODM Enhanced Features Examples")
    print("=" * 50)
    
    try:
        await example_enhanced_crud()
        await example_state_management()
        await example_query_interface()
        await example_bulk_operations()
        await example_advanced_scenarios()
        
        print("\\n" + "=" * 50)
        print("✅ All examples completed successfully!")
        print("\\nKey Features Demonstrated:")
        print("• Enhanced CRUD operations (save, replace, sync)")
        print("• Document state management and change tracking")
        print("• Type-safe query builder interface")
        print("• Bulk operations for efficient batch processing")
        print("• Merge strategies for conflict resolution")
        print("• Optimistic concurrency control with ETags")
        print("• Partial updates for efficiency")
        
    except Exception as e:
        print(f"\\n❌ Example failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    """
    To run this example:
    
    1. Install dependencies:
       pip install azure-cosmos pydantic
    
    2. Update connection string in examples
    
    3. Run:
       python examples_enhanced_features.py
    """
    
    # Run examples
    asyncio.run(main())