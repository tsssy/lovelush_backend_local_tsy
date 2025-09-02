#!/usr/bin/env python3
"""Script to seed agents and sub-accounts for testing."""

import asyncio
import os
import random
import sys
import traceback

from app.core.config.settings import settings
from app.domain.models.agent import AgentCreate, SubAccountCreate
from app.infrastructure.database.mongodb import mongodb
from app.infrastructure.database.repositories.agent_repository import (
    AgentRepository,
    SubAccountRepository,
)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 50+ unique sub-account names
SUBACCOUNT_NAMES = [
    "sarah_support",
    "mike_chat",
    "emma_help",
    "alex_care",
    "lisa_assist",
    "john_service",
    "anna_guide",
    "david_chat",
    "nina_help",
    "tom_support",
    "lucy_care",
    "paul_assist",
    "kate_service",
    "mark_guide",
    "amy_chat",
    "steve_help",
    "julia_support",
    "chris_care",
    "dana_assist",
    "ryan_service",
    "mia_guide",
    "luke_chat",
    "zoe_help",
    "ivan_support",
    "eva_care",
    "noah_assist",
    "ruby_service",
    "leo_guide",
    "cleo_chat",
    "max_help",
    "iris_support",
    "finn_care",
    "rosa_assist",
    "owen_service",
    "ivy_guide",
    "jude_chat",
    "luna_help",
    "cruz_support",
    "nora_care",
    "kai_assist",
    "ava_service",
    "eli_guide",
    "jade_chat",
    "beck_help",
    "sage_support",
    "sky_care",
    "ray_assist",
    "faye_service",
    "cole_guide",
    "sage_chat",
    "nova_help",
    "blue_support",
    "gray_care",
    "reed_assist",
    "wren_service",
]


async def seed_agents_and_subaccounts():
    """Seed 10 agents with 5 sub-accounts each."""

    try:
        # Initialize database connection
        print("🔌 Connecting to database...")
        await mongodb.connect()
        print("✅ Database connected successfully!")

        agent_repo = AgentRepository()
        sub_account_repo = SubAccountRepository()

        # Clear existing agents and sub-accounts (optional - comment out if you want to keep existing data)
        print("🧹 Clearing existing agents and sub-accounts...")
        await agent_repo.collection.delete_many({})
        await sub_account_repo.collection.delete_many({})
        print("✅ Existing data cleared!")

        # Shuffle sub-account names to ensure randomness
        available_names = SUBACCOUNT_NAMES.copy()
        random.shuffle(available_names)
        name_index = 0

        print("🚀 Creating 10 agents with 5 sub-accounts each...")

        for i in range(1, 11):  # Create 10 agents
            agent_name = f"agent-{i}"

            # Create agent
            agent_data = AgentCreate(
                name=agent_name,
                description=f"Test agent {i} for customer support",
                priority=random.randint(0, 10),
                password="pswrd123",
            )

            print(f"\n📝 Creating agent: {agent_name}")
            agent = await agent_repo.create(agent_data)
            print(f"✅ Agent created with ID: {agent.id}")

            # Create 5 sub-accounts for this agent
            for j in range(5):
                if name_index >= len(available_names):
                    print("❌ Ran out of unique sub-account names!")
                    break

                sub_account_name = available_names[name_index]
                name_index += 1

                sub_account_data = SubAccountCreate(
                    agent_id=str(agent.id),
                    name=sub_account_name,
                    display_name=sub_account_name.replace("_", " ").title(),
                    bio=f"Customer support specialist - {sub_account_name}",
                    age=random.randint(20, 35),
                    location=random.choice(
                        [
                            "San Francisco, CA",
                            "New York, NY",
                            "Los Angeles, CA",
                            "Miami, FL",
                            "Austin, TX",
                            "Seattle, WA",
                            "Chicago, IL",
                            "Boston, MA",
                            "Denver, CO",
                            "Atlanta, GA",
                        ]
                    ),
                    tags=random.sample(
                        [
                            "friendly",
                            "professional",
                            "tech-savvy",
                            "patient",
                            "multilingual",
                            "creative",
                            "problem-solver",
                            "experienced",
                            "enthusiastic",
                            "reliable",
                            "empathetic",
                            "quick-response",
                        ],
                        k=random.randint(2, 5),
                    ),
                    photo_urls=(
                        [
                            f"https://example.com/photos/{sub_account_name}_1.jpg",
                            f"https://example.com/photos/{sub_account_name}_2.jpg",
                        ]
                        if random.choice([True, False])
                        else []
                    ),
                    max_concurrent_chats=random.randint(3, 8),
                    password="pswrd123",  # Same password for all sub-accounts
                )

                sub_account = await sub_account_repo.create(sub_account_data)
                print(
                    f"  ✅ Sub-account created: {sub_account_name} (ID: {sub_account.id})"
                )

        print(f"\n🎉 Successfully created 10 agents with {name_index} sub-accounts!")
        print("\n" + "=" * 60)
        print("AUTHENTICATION CREDENTIALS:")
        print("=" * 60)
        print("\nAGENT LOGIN (for agent dashboard):")
        for i in range(1, 11):
            print(f"Agent Name: agent-{i}")
            print(f"Password: pswrd123")
            print("-" * 30)

        print(f"\nSUB-ACCOUNT LOGIN (legacy, if needed):")
        used_names = available_names[:name_index]
        for name in used_names[:10]:  # Show first 10 for brevity
            print(f"Sub-Account: {name}")
            print(f"Password: pswrd123")
            print("-" * 20)
        print(f"... and {len(used_names) - 10} more sub-accounts")

        print(f"\n📊 SUMMARY:")
        print(f"Total Agents: 10")
        print(f"Total Sub-Accounts: {name_index}")
        print(f"Agent Password: pswrd123")
        print(f"Sub-Account Password: pswrd123")

    except Exception as e:
        print(f"❌ Error during seeding: {e}")
        traceback.print_exc()

    finally:
        # Close database connection
        await mongodb.disconnect()
        print("\n🔌 Database connection closed")


if __name__ == "__main__":
    print("🌱 Starting agent and sub-account seeding...")
    print(f"Database: {settings.mongodb_name}")
    print(f"MongoDB URI: {settings.mongo_uri}")
    print("")

    asyncio.run(seed_agents_and_subaccounts())
