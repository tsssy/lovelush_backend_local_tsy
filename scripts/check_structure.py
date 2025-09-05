#!/usr/bin/env python3

import asyncio
import os
import sys
from pathlib import Path

# Add the parent directory to the Python path so we can import app modules
parent_dir = Path(__file__).parent.parent
sys.path.append(str(parent_dir))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def check_data():
    """Check current database structure"""
    client = AsyncIOMotorClient(os.getenv('MONGODB_URL'))
    db = client[os.getenv('MONGODB_NAME')]
    
    # Check agents
    agents = await db.agents.find({'deleted_at': None}).to_list(None)
    print(f'总共有 {len(agents)} 个agents:')
    for agent in agents:
        print(f'- Agent: {agent.get("name")} (id: {agent["_id"]})')
    
    # Check sub_accounts  
    sub_accounts = await db.sub_accounts.find({'deleted_at': None}).to_list(None)
    print(f'\n总共有 {len(sub_accounts)} 个sub_accounts:')
    for sub in sub_accounts:
        print(f'- {sub.get("display_name")} (agent_id: {sub.get("agent_id")}, active: {sub.get("is_active")})')
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check_data())