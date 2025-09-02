#!/usr/bin/env python3
"""
Test script for message credit consumption functionality.
Tests the core logic without requiring the full FastAPI server.
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.domain.services.app_settings_service import AppSettingsService
from app.domain.services.credits_service import CreditsService
from app.domain.services.message_credit_service import MessageCreditService


async def test_message_credit_service():
    """Test the message credit service functionality."""
    print("🧪 Testing Message Credit Service")
    print("=" * 50)

    try:
        # Initialize services
        print("1. Initializing services...")
        credits_service = CreditsService()
        app_settings_service = AppSettingsService()
        message_credit_service = MessageCreditService()

        # Test user ID
        test_user_id = "68aee0714b48d682f77f5a79"

        print(f"2. Testing with user ID: {test_user_id}")

        # Check if user can send message before setup
        print("3. Checking initial message sending capability...")
        can_send_initial = await message_credit_service.can_send_message(test_user_id)
        print(f"   Can send message (initial): {can_send_initial}")

        # Get user message status
        print("4. Getting user message status...")
        status = await message_credit_service.get_user_message_status(test_user_id)
        print(f"   Message status: {status}")

        # Try to simulate consuming message credit
        if can_send_initial:
            print("5. Testing message credit consumption...")
            try:
                consumed = await message_credit_service.consume_message_credit(
                    user_id=test_user_id, message_id="test_message_123"
                )
                print(f"   Credit consumed successfully: {consumed}")
            except Exception as e:
                print(f"   Credit consumption failed: {e}")
        else:
            print("5. User cannot send message - skipping credit consumption test")

        # Get updated status
        print("6. Getting updated message status...")
        updated_status = await message_credit_service.get_user_message_status(
            test_user_id
        )
        print(f"   Updated status: {updated_status}")

        print("\n✅ Test completed successfully!")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("Starting message credit service test...")
    asyncio.run(test_message_credit_service())
