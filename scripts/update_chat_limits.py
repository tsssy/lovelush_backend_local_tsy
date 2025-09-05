#!/usr/bin/env python3
"""
Update max_concurrent_chats for all sub_accounts
Quick script to adjust concurrent chat limits for better user coverage
"""

import os
import sys
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymongo
from pymongo import MongoClient


class ChatLimitUpdater:
    """Update max_concurrent_chats for sub_accounts"""
    
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017"):
        self.mongo_uri = mongo_uri
        self.client = MongoClient(mongo_uri)
        self.target_db = self.client["lovelush_divination"]
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()
    
    def update_chat_limits(self, new_limit: int, agent_name: str = "agent-coco"):
        """
        Update max_concurrent_chats for all sub_accounts of a specific agent
        
        Args:
            new_limit: New max_concurrent_chats value
            agent_name: Agent name (default: agent-coco)
        """
        try:
            print(f"🔄 Updating max_concurrent_chats to {new_limit} for {agent_name}'s sub_accounts...")
            print("-" * 60)
            
            # Find the agent first
            agent = self.target_db.agents.find_one({"name": agent_name})
            if not agent:
                print(f"❌ Agent '{agent_name}' not found!")
                return False
            
            # Find all sub_accounts for this agent
            sub_accounts = list(self.target_db.sub_accounts.find({"agent_id": str(agent["_id"])}))
            
            if not sub_accounts:
                print(f"❌ No sub_accounts found for agent '{agent_name}'!")
                return False
            
            print(f"📋 Found {len(sub_accounts)} sub_accounts to update:")
            
            # Update each sub_account
            updated_count = 0
            for sub_account in sub_accounts:
                old_limit = sub_account.get("max_concurrent_chats", "unknown")
                
                # Update the document
                result = self.target_db.sub_accounts.update_one(
                    {"_id": sub_account["_id"]},
                    {
                        "$set": {
                            "max_concurrent_chats": new_limit,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                
                if result.modified_count > 0:
                    print(f"✅ {sub_account['display_name']}: {old_limit} → {new_limit}")
                    updated_count += 1
                else:
                    print(f"⚠️ {sub_account['display_name']}: No change needed")
            
            print(f"\n🎉 Successfully updated {updated_count} sub_accounts!")
            return True
            
        except Exception as e:
            print(f"❌ Error updating chat limits: {str(e)}")
            return False
    
    def show_current_limits(self, agent_name: str = "agent-coco"):
        """Show current max_concurrent_chats for all sub_accounts"""
        try:
            print(f"📊 Current chat limits for {agent_name}'s sub_accounts:")
            print("-" * 50)
            
            # Find the agent
            agent = self.target_db.agents.find_one({"name": agent_name})
            if not agent:
                print(f"❌ Agent '{agent_name}' not found!")
                return
            
            # Find sub_accounts
            sub_accounts = list(self.target_db.sub_accounts.find({"agent_id": str(agent["_id"])}))
            
            if not sub_accounts:
                print(f"❌ No sub_accounts found for agent '{agent_name}'!")
                return
            
            for sub_account in sub_accounts:
                current_limit = sub_account.get("max_concurrent_chats", "not set")
                current_count = sub_account.get("current_chat_count", 0)
                status = sub_account.get("status", "unknown")
                
                print(f"  {sub_account['display_name']}:")
                print(f"    Max concurrent: {current_limit}")
                print(f"    Current count: {current_count}")
                print(f"    Status: {status}")
                print()
                
        except Exception as e:
            print(f"❌ Error showing current limits: {str(e)}")


def main():
    """Main update function with interactive prompt"""
    print("🚀 Chat Limit Updater for Sub_accounts")
    print("=" * 50)
    
    with ChatLimitUpdater() as updater:
        # Show current limits first
        updater.show_current_limits()
        
        # Get user input for new limit
        try:
            print("\n💡 Suggested values:")
            print("  - 10-20: Medium scale (50-100 total concurrent users)")
            print("  - 50-100: Large scale (250-500 total concurrent users)")
            print("  - 1000+: No practical limit")
            
            new_limit = int(input("\nEnter new max_concurrent_chats value: "))
            
            if new_limit <= 0:
                print("❌ Value must be positive!")
                return
            
            print(f"\n🔄 Setting max_concurrent_chats to {new_limit} for all 5 sub_accounts...")
            print(f"📊 This will allow up to {new_limit * 5} total concurrent chats across all specialists.")
            
            confirm = input("\nProceed? (y/N): ").lower().strip()
            if confirm == 'y':
                success = updater.update_chat_limits(new_limit)
                
                if success:
                    print(f"\n🎉 Update completed! All sub_accounts can now handle {new_limit} concurrent chats each.")
                    print(f"📈 Total system capacity: {new_limit * 5} concurrent users")
                else:
                    print(f"\n❌ Update failed!")
            else:
                print("❌ Update cancelled.")
                
        except ValueError:
            print("❌ Please enter a valid number!")
        except KeyboardInterrupt:
            print("\n❌ Update cancelled by user.")


if __name__ == "__main__":
    main()