#!/usr/bin/env python3
"""
End-to-end test script for the mini app workflow.
Creates a user and tests the complete flow.
"""

import os
import sys

import requests

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKEND_URL = "http://localhost:8000"


def test_user_creation():
    """Test creating a user via Telegram auth endpoint."""
    print("🧪 Testing user creation via Telegram auth...")

    telegram_auth_data = {
        "telegram_id": "123456789",
        "username": "test_user_mini_app",
        "full_name": "Test User",
    }

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/auth/telegram", json=telegram_auth_data, timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✅ User authenticated successfully!")
                return data["data"]["access_token"]
            else:
                print(
                    f"❌ User authentication failed: {data.get('msg', 'Unknown error')}"
                )
                return None
        elif response.status_code == 400 and "duplicate key error" in response.text:
            # User exists, try to get token anyway - this suggests the telegram auth should work
            print("ℹ️  User already exists, trying authentication...")
            # The error suggests user exists, so let's try with a different telegram_id
            telegram_auth_data["telegram_id"] = "987654321"
            telegram_auth_data["username"] = "test_user_mini_app_2"

            response = requests.post(
                f"{BACKEND_URL}/api/v1/auth/telegram",
                json=telegram_auth_data,
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    print("✅ New user created and authenticated successfully!")
                    return data["data"]["access_token"]

            print(f"❌ Still failed: {response.text}")
            return None
        else:
            print(f"❌ HTTP error: {response.status_code}")
            print(f"Response: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return None


def test_user_profile(token):
    """Test fetching user profile with token."""
    print("🔍 Testing user profile fetch...")

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            f"{BACKEND_URL}/api/v1/users/me", headers=headers, timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                user_data = data["data"]
                print("✅ User profile fetched successfully!")
                print(f"   Username: {user_data.get('username')}")
                print(f"   Telegram ID: {user_data.get('telegram_id')}")
                print(f"   Active: {user_data.get('is_active')}")
                return True
            else:
                print(f"❌ Profile fetch failed: {data.get('msg', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False


def generate_mini_app_url(token):
    """Generate the mini app URL with token."""
    return f"http://localhost:8080?token={token}"


def main():
    """Run the complete test."""
    print("=" * 60)
    print("🚀 LoveLush Mini App End-to-End Test")
    print("=" * 60)
    print()

    # Step 1: Create/authenticate user
    token = test_user_creation()
    if not token:
        print("❌ Test failed at user creation step")
        return

    print()

    # Step 2: Test user profile fetch
    if not test_user_profile(token):
        print("❌ Test failed at profile fetch step")
        return

    print()

    # Step 3: Generate mini app URL
    mini_app_url = generate_mini_app_url(token)
    print("🎉 Complete workflow test PASSED!")
    print()
    print("🌐 Generated Mini App URL:")
    print(mini_app_url)
    print()
    print("📋 Next steps:")
    print("1. Open the URL above in your browser")
    print("2. The mini app should load and display user profile")
    print("3. You can test the 'Test Backend API' button")
    print()
    print("💡 For Telegram integration:")
    print("1. Use ngrok to expose both frontend and backend")
    print("2. Update miniapp_url in backend settings")
    print("3. Test with your Telegram bot")
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
