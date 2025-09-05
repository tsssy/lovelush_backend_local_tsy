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

async def fix_match_config():
    """Fix match configuration to provide 5 initial free matches"""
    client = AsyncIOMotorClient(os.getenv('MONGODB_URL'))
    db = client[os.getenv('MONGODB_NAME')]
    
    # Check current config
    app_settings = await db.app_settings.find_one({})
    if app_settings:
        current_config = app_settings.get('match_config', {})
        print('当前Match配置:')
        print(f'- initial_free_matches: {current_config.get("initial_free_matches", "未设置")}')
        print(f'- daily_free_matches: {current_config.get("daily_free_matches", "未设置")}')
        print(f'- cost_per_match: {current_config.get("cost_per_match", "未设置")}')
        
        # Update to provide 5 initial free matches
        new_match_config = {
            "initial_free_matches": 5,  # 确保新用户能免费获得5个matches
            "daily_free_matches": 1,    # 保持每日免费match
            "cost_per_match": 5         # 保持付费match价格
        }
        
        # Update app_settings
        await db.app_settings.update_one(
            {},
            {"$set": {"match_config": new_match_config}},
            upsert=True
        )
        
        print(f'\n✅ 已更新Match配置:')
        print(f'- initial_free_matches: {new_match_config["initial_free_matches"]}')
        print(f'- daily_free_matches: {new_match_config["daily_free_matches"]}')
        print(f'- cost_per_match: {new_match_config["cost_per_match"]}')
        
    else:
        # Create new app_settings
        new_app_settings = {
            "match_config": {
                "initial_free_matches": 5,
                "daily_free_matches": 1,
                "cost_per_match": 5
            }
        }
        
        await db.app_settings.insert_one(new_app_settings)
        print('✅ 创建了新的app_settings配置')
    
    client.close()
    print('\n🎯 现在新用户应该能免费获得5个initial matches')

if __name__ == "__main__":
    asyncio.run(fix_match_config())