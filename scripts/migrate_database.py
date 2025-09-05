#!/usr/bin/env python3
"""
Database Migration Script
Migrate data from lovelush database to lovelush_divination database
"""

import os
import sys
from typing import Dict, List, Optional
from datetime import datetime

# Add the project root to sys.path so we can import from app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymongo
from pymongo import MongoClient
from bson import ObjectId


class DatabaseMigrator:
    """Handle database migration from lovelush to lovelush_divination"""
    
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017"):
        self.mongo_uri = mongo_uri
        self.client = MongoClient(mongo_uri)
        self.source_db = self.client["lovelush"]
        self.target_db = self.client["lovelush_divination"]
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()
    
    def migrate_user_by_telegram_id(self, telegram_id: str) -> bool:
        """
        Migrate a specific user by their Telegram ID
        
        Args:
            telegram_id: The telegram_id of the user to migrate
            
        Returns:
            bool: True if migration successful, False otherwise
        """
        try:
            print(f"🔍 Searching for user with telegram_id: {telegram_id}")
            
            # Find user in source database
            user_doc = self.source_db.users.find_one({"telegram_id": telegram_id})
            
            if not user_doc:
                print(f"❌ User with telegram_id {telegram_id} not found in source database")
                return False
            
            print(f"✅ Found user: {user_doc.get('username', 'N/A')} (ID: {user_doc['_id']})")
            
            # Check if user already exists in target database
            existing_user = self.target_db.users.find_one({"telegram_id": telegram_id})
            if existing_user:
                print(f"⚠️ User already exists in target database. Updating...")
                # Update existing user
                result = self.target_db.users.replace_one(
                    {"telegram_id": telegram_id}, 
                    user_doc
                )
                print(f"✅ Updated user in target database: {result.modified_count} document(s)")
            else:
                # Insert new user
                result = self.target_db.users.insert_one(user_doc)
                print(f"✅ Inserted user into target database with ID: {result.inserted_id}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error migrating user: {str(e)}")
            return False
    
    def migrate_collection(self, collection_name: str, query: Dict = None) -> int:
        """
        Migrate an entire collection or documents matching a query
        
        Args:
            collection_name: Name of the collection to migrate
            query: Optional query to filter documents (default: migrate all)
            
        Returns:
            int: Number of documents migrated
        """
        try:
            print(f"🔄 Migrating collection: {collection_name}")
            
            source_collection = self.source_db[collection_name]
            target_collection = self.target_db[collection_name]
            
            # Find documents to migrate
            if query is None:
                query = {}
            
            documents = list(source_collection.find(query))
            
            if not documents:
                print(f"⚠️ No documents found in {collection_name} with query: {query}")
                return 0
            
            print(f"📦 Found {len(documents)} document(s) to migrate")
            
            # Insert documents into target database
            if len(documents) == 1:
                result = target_collection.insert_one(documents[0])
                print(f"✅ Inserted 1 document with ID: {result.inserted_id}")
                return 1
            else:
                result = target_collection.insert_many(documents)
                print(f"✅ Inserted {len(result.inserted_ids)} documents")
                return len(result.inserted_ids)
            
        except Exception as e:
            print(f"❌ Error migrating collection {collection_name}: {str(e)}")
            return 0
    
    def list_collections(self, database_name: str = "source") -> List[str]:
        """List all collections in the specified database"""
        try:
            if database_name == "source":
                db = self.source_db
            else:
                db = self.target_db
                
            collections = db.list_collection_names()
            print(f"📋 Collections in {database_name} database ({db.name}):")
            for collection in collections:
                count = db[collection].count_documents({})
                print(f"  - {collection}: {count} documents")
            
            return collections
            
        except Exception as e:
            print(f"❌ Error listing collections: {str(e)}")
            return []
    
    def verify_migration(self, telegram_id: str) -> bool:
        """
        Verify that the user migration was successful
        
        Args:
            telegram_id: The telegram_id to verify
            
        Returns:
            bool: True if verification successful
        """
        try:
            print(f"🔍 Verifying migration for telegram_id: {telegram_id}")
            
            # Check source
            source_user = self.source_db.users.find_one({"telegram_id": telegram_id})
            target_user = self.target_db.users.find_one({"telegram_id": telegram_id})
            
            if not source_user:
                print(f"❌ Source user not found")
                return False
                
            if not target_user:
                print(f"❌ Target user not found - migration failed")
                return False
            
            # Compare key fields
            source_fields = {
                "username": source_user.get("username"),
                "telegram_id": source_user.get("telegram_id"),
                "created_at": source_user.get("created_at"),
                "is_active": source_user.get("is_active")
            }
            
            target_fields = {
                "username": target_user.get("username"),
                "telegram_id": target_user.get("telegram_id"),
                "created_at": target_user.get("created_at"),
                "is_active": target_user.get("is_active")
            }
            
            if source_fields == target_fields:
                print("✅ Migration verification successful - key fields match")
                return True
            else:
                print("❌ Migration verification failed - fields don't match")
                print(f"Source: {source_fields}")
                print(f"Target: {target_fields}")
                return False
                
        except Exception as e:
            print(f"❌ Error verifying migration: {str(e)}")
            return False


def main():
    """Main migration function"""
    print("🚀 Starting database migration from lovelush to lovelush_divination")
    print("=" * 60)
    
    # User data from the image
    TARGET_TELEGRAM_ID = "8107272400"  # danielyu233 user
    
    with DatabaseMigrator() as migrator:
        # List collections in both databases
        print("\n📋 Current database status:")
        print("-" * 30)
        migrator.list_collections("source")
        print()
        migrator.list_collections("target")
        
        print(f"\n🎯 Migrating user with telegram_id: {TARGET_TELEGRAM_ID}")
        print("-" * 40)
        
        # Migrate the specific user
        success = migrator.migrate_user_by_telegram_id(TARGET_TELEGRAM_ID)
        
        if success:
            print("\n🔍 Verifying migration...")
            verification_success = migrator.verify_migration(TARGET_TELEGRAM_ID)
            
            if verification_success:
                print("\n🎉 Migration completed successfully!")
                print("✅ User data migrated and verified")
            else:
                print("\n⚠️ Migration completed but verification failed")
        else:
            print("\n❌ Migration failed")
    
    print("\n" + "=" * 60)
    print("Migration process completed.")


if __name__ == "__main__":
    main()