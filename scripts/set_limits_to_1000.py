#!/usr/bin/env python3
"""
Set max_concurrent_chats to 1000 for all agent-coco sub_accounts
Direct update without interactive input
"""

import os
import sys
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymongo
from pymongo import MongoClient


def update_to_1000():
    """Update all agent-coco sub_accounts to max_concurrent_chats = 1000"""
    
    client = MongoClient("mongodb://localhost:27017")
    target_db = client["lovelush_divination"]
    
    try:
        print("🚀 Updating max_concurrent_chats to 1000 for all agent-coco sub_accounts")
        print("=" * 70)
        
        # Find agent-coco
        agent = target_db.agents.find_one({"name": "agent-coco"})
        if not agent:
            print("❌ Agent 'agent-coco' not found!")
            return
        
        print(f"✅ Found agent-coco (ID: {agent['_id']})")
        
        # Find all sub_accounts for agent-coco
        sub_accounts = list(target_db.sub_accounts.find({"agent_id": str(agent["_id"])}))
        
        if not sub_accounts:
            print("❌ No sub_accounts found for agent-coco!")
            return
        
        print(f"📋 Found {len(sub_accounts)} sub_accounts to update:")
        
        # Update each sub_account
        updated_count = 0
        for sub_account in sub_accounts:
            old_limit = sub_account.get("max_concurrent_chats", "unknown")
            
            result = target_db.sub_accounts.update_one(
                {"_id": sub_account["_id"]},
                {
                    "$set": {
                        "max_concurrent_chats": 1000,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                print(f"✅ {sub_account['display_name']}: {old_limit} → 1000")
                updated_count += 1
            else:
                print(f"⚠️ {sub_account['display_name']}: Already set to 1000")
        
        print(f"\n🎉 Successfully updated {updated_count} sub_accounts!")
        print(f"📈 New system capacity: 5,000 concurrent users (5 accounts × 1000 each)")
        print("🔓 Practically unlimited concurrent chat capacity achieved!")
        
        # Verify the update
        print(f"\n🔍 Verification:")
        updated_sub_accounts = list(target_db.sub_accounts.find({"agent_id": str(agent["_id"])}))
        for sub in updated_sub_accounts:
            print(f"  {sub['display_name']}: max_concurrent_chats = {sub['max_concurrent_chats']}")
            
    except Exception as e:
        print(f"❌ Error updating chat limits: {str(e)}")
    finally:
        client.close()


if __name__ == "__main__":
    update_to_1000()