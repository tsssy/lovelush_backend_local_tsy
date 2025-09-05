#!/usr/bin/env python3

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add the parent directory to the Python path
parent_dir = Path(__file__).parent.parent
sys.path.append(str(parent_dir))

from app.infrastructure.database.repositories.app_settings_repository import AppSettingsRepository
from app.domain.models.settings import MatchConfiguration
from app.infrastructure.database.mongodb import mongodb
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def fix_match_settings():
    """Fix match settings to ensure 5 initial free matches"""
    print("=== 修复Match配置 ===")
    
    # Initialize database connection
    await mongodb.connect()
    
    try:
        # Initialize repository
        app_settings_repo = AppSettingsRepository()
        
        # Get current settings
        current_settings = await app_settings_repo.get_default_settings()
        
        if current_settings:
            print("当前配置:")
            print(f"- initial_free_matches: {current_settings.match_config.initial_free_matches}")
            print(f"- daily_free_matches: {current_settings.match_config.daily_free_matches}")
            print(f"- cost_per_match: {current_settings.match_config.cost_per_match}")
            
            # Check if already correct
            if current_settings.match_config.initial_free_matches == 5:
                print("\n✅ 配置已经正确，无需修改")
                return
            
            # Update match config
            current_settings.match_config.initial_free_matches = 5
            current_settings.match_config.daily_free_matches = 1  
            current_settings.match_config.cost_per_match = 5
            
            # Save updated settings
            updated_settings = await app_settings_repo.update(
                str(current_settings.id), 
                {"match_config": current_settings.match_config.model_dump()}
            )
            
            if updated_settings:
                print("\n✅ 配置已更新:")
                print(f"- initial_free_matches: {updated_settings.match_config.initial_free_matches}")
                print(f"- daily_free_matches: {updated_settings.match_config.daily_free_matches}")
                print(f"- cost_per_match: {updated_settings.match_config.cost_per_match}")
            else:
                print("❌ 更新失败")
                
        else:
            print("未找到默认配置，创建新的...")
            from app.domain.models.settings import AppSettingsCreate, CoinConfiguration, MessageConfiguration
            
            # Create new default settings
            new_settings = AppSettingsCreate(
                name="default",
                description="Default app settings with 5 initial free matches",
                coin_config=CoinConfiguration(initial_free_coins=100),
                message_config=MessageConfiguration(cost_per_message=10, initial_free_messages=0),
                match_config=MatchConfiguration(
                    initial_free_matches=5,  # 确保是5个
                    daily_free_matches=1,
                    cost_per_match=5
                ),
                is_active=True,
                is_default=True
            )
            
            created_settings = await app_settings_repo.create(new_settings)
            if created_settings:
                print("✅ 创建了新的默认配置:")
                print(f"- initial_free_matches: {created_settings.match_config.initial_free_matches}")
                print(f"- daily_free_matches: {created_settings.match_config.daily_free_matches}")
                print(f"- cost_per_match: {created_settings.match_config.cost_per_match}")
            else:
                print("❌ 创建失败")

        print("\n🎯 现在新用户应该能获得5个初始免费matches")
        
    finally:
        # Close database connection
        await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(fix_match_settings())