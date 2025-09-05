#!/usr/bin/env python3
"""
Data Restructuring Script for Divination Agents
Create agent-coco and 5 corresponding sub_accounts based on provided requirements
"""

import os
import sys
from typing import Dict, List
from datetime import datetime
import bcrypt

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymongo
from pymongo import MongoClient
from bson import ObjectId


class DivinationDataRestructurer:
    """Create structured data for divination agents and sub_accounts"""
    
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017"):
        self.mongo_uri = mongo_uri
        self.client = MongoClient(mongo_uri)
        self.target_db = self.client["lovelush_divination"]
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def _create_agent_data(self, name: str, password: str, description: str = None) -> Dict:
        """Create agent document with proper structure"""
        now = datetime.utcnow()
        
        return {
            "_id": ObjectId(),
            "deleted_at": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "name": name,
            "description": description or f"Divination agent - {name}",
            "status": "active",
            "role": "agent",
            "priority": 1,
            "hashed_password": self._hash_password(password),
            "last_assigned_sub_account_index": -1
        }
    
    def _create_sub_account_data(self, agent_id: ObjectId, display_name: str, tags: List[str], 
                                name: str = None, bio: str = None, age: int = None, 
                                location: str = None) -> Dict:
        """Create sub_account document with proper structure"""
        now = datetime.utcnow()
        
        # Generate name if not provided
        if not name:
            name = display_name.lower().replace(' ', '_')
        
        return {
            "_id": ObjectId(),
            "last_activity_at": None,
            "deleted_at": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "name": name,
            "display_name": display_name,
            "status": "available",
            "avatar_url": None,
            "bio": bio or f"Divination specialist - {display_name}",
            "age": age or 25,  # Default age
            "location": location or "Mystic Realm",  # Default location
            "gender": None,
            "photo_urls": [
                f"https://example.com/photos/{name}_1.jpg",
                f"https://example.com/photos/{name}_2.jpg"
            ],
            "tags": tags,
            "max_concurrent_chats": 3,  # Default for divination specialists
            "agent_id": str(agent_id),
            "hashed_password": self._hash_password("default123"),  # Default password
            "current_chat_count": 0
        }
    
    def create_divination_data(self) -> bool:
        """
        Create agent-coco and 5 corresponding sub_accounts for divination services
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print("🔮 Creating divination agent and sub_accounts...")
            print("=" * 60)
            
            # 1. Create agent-coco
            agent_data = self._create_agent_data(
                name="agent-coco",
                password="coco123",
                description="Divination services agent - coco"
            )
            
            print(f"📝 Creating agent: {agent_data['name']}")
            
            # Check if agent already exists
            existing_agent = self.target_db.agents.find_one({"name": "agent-coco"})
            if existing_agent:
                print("⚠️ Agent 'agent-coco' already exists. Updating...")
                agent_data["_id"] = existing_agent["_id"]
                self.target_db.agents.replace_one({"name": "agent-coco"}, agent_data)
                agent_id = existing_agent["_id"]
            else:
                result = self.target_db.agents.insert_one(agent_data)
                agent_id = result.inserted_id
                print(f"✅ Created agent with ID: {agent_id}")
            
            # 2. Create 5 sub_accounts for the agent
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
            
            created_sub_accounts = []
            
            for i, sub_data in enumerate(sub_accounts_data, 1):
                print(f"📝 Creating sub_account {i}: {sub_data['display_name']}")
                
                sub_account_doc = self._create_sub_account_data(
                    agent_id=agent_id,
                    display_name=sub_data["display_name"],
                    tags=sub_data["tags"],
                    bio=sub_data.get("bio"),
                    age=sub_data.get("age"),
                    location=sub_data.get("location")
                )
                
                # Check if sub_account already exists
                existing_sub = self.target_db.sub_accounts.find_one({
                    "display_name": sub_data["display_name"]
                })
                
                if existing_sub:
                    print(f"⚠️ Sub_account '{sub_data['display_name']}' already exists. Updating...")
                    sub_account_doc["_id"] = existing_sub["_id"]
                    self.target_db.sub_accounts.replace_one(
                        {"display_name": sub_data["display_name"]}, 
                        sub_account_doc
                    )
                    created_sub_accounts.append(existing_sub["_id"])
                else:
                    result = self.target_db.sub_accounts.insert_one(sub_account_doc)
                    created_sub_accounts.append(result.inserted_id)
                    print(f"✅ Created sub_account with ID: {result.inserted_id}")
            
            print(f"\n🎉 Successfully created/updated:")
            print(f"  - 1 agent (agent-coco)")
            print(f"  - {len(created_sub_accounts)} sub_accounts")
            print(f"  - Agent ID: {agent_id}")
            print(f"  - Sub_account IDs: {[str(id) for id in created_sub_accounts]}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error creating divination data: {str(e)}")
            return False
    
    def verify_created_data(self) -> bool:
        """
        Verify that the created data is properly structured
        
        Returns:
            bool: True if verification successful
        """
        try:
            print("\n🔍 Verifying created data...")
            print("-" * 40)
            
            # Check agent
            agent = self.target_db.agents.find_one({"name": "agent-coco"})
            if not agent:
                print("❌ Agent 'agent-coco' not found")
                return False
            
            print(f"✅ Agent found: {agent['name']}")
            print(f"  - Status: {agent['status']}")
            print(f"  - Role: {agent['role']}")
            print(f"  - Password hash present: {bool(agent.get('hashed_password'))}")
            
            # Check sub_accounts
            sub_accounts = list(self.target_db.sub_accounts.find({"agent_id": str(agent["_id"])}))
            
            if len(sub_accounts) != 5:
                print(f"❌ Expected 5 sub_accounts, found {len(sub_accounts)}")
                return False
            
            print(f"✅ Found {len(sub_accounts)} sub_accounts:")
            for sub in sub_accounts:
                print(f"  - {sub['display_name']}: {', '.join(sub['tags'])}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error verifying data: {str(e)}")
            return False


def main():
    """Main restructuring function"""
    print("🚀 Starting divination data restructuring")
    print("Creating agent-coco with 5 specialized sub_accounts")
    print("=" * 60)
    
    with DivinationDataRestructurer() as restructurer:
        # Create the data
        success = restructurer.create_divination_data()
        
        if success:
            # Verify the data
            verification_success = restructurer.verify_created_data()
            
            if verification_success:
                print("\n🎉 Data restructuring completed successfully!")
                print("✅ All data created and verified")
            else:
                print("\n⚠️ Data created but verification failed")
        else:
            print("\n❌ Data restructuring failed")
    
    print("\n" + "=" * 60)
    print("Restructuring process completed.")


if __name__ == "__main__":
    main()