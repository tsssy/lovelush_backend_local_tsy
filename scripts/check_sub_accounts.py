#!/usr/bin/env python3

import asyncio
import sys
from pathlib import Path

parent_dir = Path(__file__).parent.parent
sys.path.append(str(parent_dir))

from app.infrastructure.database.mongodb import mongodb
from dotenv import load_dotenv

load_dotenv()

async def check_sub_accounts():
    """Check available sub_accounts in database"""
    await mongodb.connect()
    
    try:
        db = mongodb.get_database()
        
        # Check all sub_accounts
        sub_accounts = await db.sub_accounts.find({"deleted_at": None}).to_list(None)
        print(f"总共有 {len(sub_accounts)} 个sub_accounts:")
        
        active_count = 0
        for sub in sub_accounts:
            is_active = sub.get('is_active', False)
            status = sub.get('status', 'unknown')
            if is_active:
                active_count += 1
            
            print(f"- {sub.get('display_name', 'No name')}: active={is_active}, status={status}")
        
        print(f"\n其中 {active_count} 个是活跃的")
        
        # Check agents
        agents = await db.agents.find({"deleted_at": None}).to_list(None)
        print(f"\n总共有 {len(agents)} 个agents:")
        for agent in agents:
            print(f"- {agent.get('name', 'No name')}: active={agent.get('is_active', False)}")
            
        return active_count
        
    finally:
        await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(check_sub_accounts())