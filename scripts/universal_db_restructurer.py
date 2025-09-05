#!/usr/bin/env python3
"""
Universal Database Restructuring Template
Template script for recreating lovelush_divination database structure
Can be customized and reused across different environments
"""

import os
import sys
from typing import Dict, List, Optional
from datetime import datetime
import bcrypt

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymongo
from pymongo import MongoClient
from bson import ObjectId


class UniversalDataRestructurer:
    """Universal data restructuring template for lovelush_divination database"""
    
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017", target_db_name: str = "lovelush_divination"):
        self.mongo_uri = mongo_uri
        self.target_db_name = target_db_name
        self.client = MongoClient(mongo_uri)
        self.target_db = self.client[target_db_name]
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def create_agent(self, name: str, password: str, description: str = None, 
                    priority: int = 1, status: str = "active") -> ObjectId:
        """
        Create an agent with standard structure
        
        Args:
            name: Agent name (must be unique)
            password: Plain text password (will be hashed)
            description: Agent description
            priority: Agent priority (default: 1)
            status: Agent status (default: "active")
            
        Returns:
            ObjectId: The created agent's ID
        """
        now = datetime.utcnow()
        
        agent_data = {
            "_id": ObjectId(),
            "deleted_at": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "name": name,
            "description": description or f"Agent - {name}",
            "status": status,
            "role": "agent",
            "priority": priority,
            "hashed_password": self._hash_password(password),
            "last_assigned_sub_account_index": -1
        }
        
        # Check if agent already exists
        existing_agent = self.target_db.agents.find_one({"name": name})
        if existing_agent:
            print(f"⚠️ Agent '{name}' already exists. Updating...")
            agent_data["_id"] = existing_agent["_id"]
            agent_data["created_at"] = existing_agent["created_at"]  # Keep original creation time
            self.target_db.agents.replace_one({"name": name}, agent_data)
            return existing_agent["_id"]
        else:
            result = self.target_db.agents.insert_one(agent_data)
            print(f"✅ Created agent '{name}' with ID: {result.inserted_id}")
            return result.inserted_id
    
    def create_sub_account(self, agent_id: ObjectId, display_name: str, tags: List[str],
                          name: str = None, bio: str = None, age: int = None,
                          location: str = None, password: str = "default123",
                          max_concurrent_chats: int = 3, status: str = "available") -> ObjectId:
        """
        Create a sub_account with standard structure
        
        Args:
            agent_id: Parent agent's ObjectId
            display_name: Display name for the sub_account
            tags: List of specialization tags
            name: Account name (auto-generated if not provided)
            bio: Biography/description
            age: Age (optional, default: 25)
            location: Location (default: "Unknown")
            password: Plain text password (default: "default123")
            max_concurrent_chats: Max concurrent chats (default: 3)
            status: Account status (default: "available")
            
        Returns:
            ObjectId: The created sub_account's ID
        """
        now = datetime.utcnow()
        
        # Generate name if not provided
        if not name:
            name = display_name.lower().replace(' ', '_').replace('[', '').replace(']', '')
        
        sub_account_data = {
            "_id": ObjectId(),
            "last_activity_at": None,
            "deleted_at": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "name": name,
            "display_name": display_name,
            "status": status,
            "avatar_url": None,
            "bio": bio or f"Specialist - {display_name}",
            "age": age if age is not None else 25,
            "location": location or "Unknown",
            "gender": None,
            "photo_urls": [
                f"https://example.com/photos/{name}_1.jpg",
                f"https://example.com/photos/{name}_2.jpg"
            ],
            "tags": tags,
            "max_concurrent_chats": max_concurrent_chats,
            "agent_id": str(agent_id),
            "hashed_password": self._hash_password(password),
            "current_chat_count": 0
        }
        
        # Check if sub_account already exists
        existing_sub = self.target_db.sub_accounts.find_one({"display_name": display_name})
        if existing_sub:
            print(f"⚠️ Sub_account '{display_name}' already exists. Updating...")
            sub_account_data["_id"] = existing_sub["_id"]
            sub_account_data["created_at"] = existing_sub["created_at"]  # Keep original creation time
            self.target_db.sub_accounts.replace_one({"display_name": display_name}, sub_account_data)
            return existing_sub["_id"]
        else:
            result = self.target_db.sub_accounts.insert_one(sub_account_data)
            print(f"✅ Created sub_account '{display_name}' with ID: {result.inserted_id}")
            return result.inserted_id
    
    def create_divination_structure(self):
        """Create the complete divination structure (agent-coco + 5 sub_accounts)"""
        print("🔮 Creating complete divination structure...")
        print("=" * 60)
        
        # Create agent-coco
        agent_id = self.create_agent(
            name="agent-coco",
            password="coco123",
            description="Divination services agent - coco",
            priority=1
        )
        
        # Sub_accounts data based on requirements
        sub_accounts_data = [
            {
                "display_name": "Anya Greene",
                "tags": ["Western Astrology", "Tarot Card"],
                "bio": "Expert in Western Astrology and Tarot Card readings with over 10 years of experience.",
                "age": 32,
                "location": "Salem, MA"
            },
            {
                "display_name": "Daniel Chen", 
                "tags": ["Bazi (Four pillars)", "I Ching"],
                "bio": "Master of Chinese metaphysics specializing in Bazi analysis and I Ching divination.",
                "age": 45,
                "location": "Hong Kong"
            },
            {
                "display_name": "Arjun Mehta",
                "tags": ["Vedic Astrology"],
                "bio": "Traditional Vedic astrologer with deep knowledge of ancient Sanskrit texts.",
                "age": 38,
                "location": "Varanasi, India"
            },
            {
                "display_name": "Kavita Patel",
                "tags": ["Vedic Astrology"],
                "bio": "Certified Vedic astrologer specializing in life guidance and spiritual counseling.",
                "age": 29,
                "location": "Mumbai, India"
            },
            {
                "display_name": "Chronos [AI]",
                "tags": ["Western Astrology", "Tarot Card", "Numerology", "Vedic Astrology", "Bazi", "I Ching"],
                "bio": "Advanced AI divination specialist with comprehensive knowledge across all systems.",
                "age": None,  # AI doesn't have age
                "location": "Digital Realm"
            }
        ]
        
        # Create sub_accounts
        sub_account_ids = []
        for sub_data in sub_accounts_data:
            sub_id = self.create_sub_account(
                agent_id=agent_id,
                display_name=sub_data["display_name"],
                tags=sub_data["tags"],
                bio=sub_data.get("bio"),
                age=sub_data.get("age"),
                location=sub_data.get("location")
            )
            sub_account_ids.append(sub_id)
        
        print(f"\n🎉 Successfully created/updated:")
        print(f"  - 1 agent (agent-coco): {agent_id}")
        print(f"  - {len(sub_account_ids)} sub_accounts: {[str(id) for id in sub_account_ids]}")
        
        return agent_id, sub_account_ids
    
    def verify_database_structure(self) -> bool:
        """Verify the complete database structure"""
        print("\n🔍 Verifying database structure...")
        print("-" * 50)
        
        try:
            # Check collections exist
            collections = self.target_db.list_collection_names()
            required_collections = ["agents", "sub_accounts"]
            
            for collection in required_collections:
                if collection in collections:
                    count = self.target_db[collection].count_documents({})
                    print(f"✅ {collection}: {count} documents")
                else:
                    print(f"❌ {collection}: collection not found")
                    return False
            
            # Check agent-coco specifically
            agent = self.target_db.agents.find_one({"name": "agent-coco"})
            if agent:
                print(f"✅ agent-coco found with {len(list(self.target_db.sub_accounts.find({'agent_id': str(agent['_id'])})))} sub_accounts")
            else:
                print("❌ agent-coco not found")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Verification error: {str(e)}")
            return False
    
    def clean_database(self):
        """Clean/reset the database (use with caution!)"""
        print("⚠️ Cleaning database collections...")
        
        try:
            self.target_db.agents.delete_many({})
            self.target_db.sub_accounts.delete_many({})
            print("✅ Database cleaned")
        except Exception as e:
            print(f"❌ Error cleaning database: {str(e)}")


def main():
    """Main function with command line options"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Universal Database Restructuring Tool")
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017", help="MongoDB URI")
    parser.add_argument("--database", default="lovelush_divination", help="Target database name")
    parser.add_argument("--clean", action="store_true", help="Clean database before restructuring")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing structure")
    
    args = parser.parse_args()
    
    print("🚀 Universal Database Restructuring Tool")
    print(f"Target: {args.mongo_uri}/{args.database}")
    print("=" * 60)
    
    with UniversalDataRestructurer(args.mongo_uri, args.database) as restructurer:
        if args.verify_only:
            # Only verify
            restructurer.verify_database_structure()
        else:
            # Full restructuring
            if args.clean:
                restructurer.clean_database()
            
            agent_id, sub_account_ids = restructurer.create_divination_structure()
            success = restructurer.verify_database_structure()
            
            if success:
                print("\n🎉 Database restructuring completed successfully!")
            else:
                print("\n⚠️ Restructuring completed but verification failed")
    
    print("\n" + "=" * 60)
    print("Process completed.")


if __name__ == "__main__":
    main()