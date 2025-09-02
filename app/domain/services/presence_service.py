"""Pusher presence service for checking channel subscriptions."""

from typing import Dict, List, Optional

from app.core.logging import get_logger
from app.infrastructure.database.repositories.user_repository import UserRepository
from app.integrations.pusher.client import pusher_client
from app.interfaces.telegram.services.notification_service import (
    telegram_notification_service,
)

logger = get_logger(__name__)


class PusherPresenceService:
    """Service for checking user presence via Pusher's presence API."""

    def __init__(self, user_repository: Optional[UserRepository] = None):
        """Initialize Pusher presence service with dependencies."""
        # Dependency injection
        self.user_repository = user_repository or UserRepository()
        self.telegram_service = telegram_notification_service

    async def is_user_subscribed_to_channel(
        self, channel_name: str, user_id: str
    ) -> bool:
        """
        Check if a specific user is subscribed to a channel.

        Args:
            channel_name: Name of the channel to check
            user_id: User ID to check for subscription

        Returns:
            True if user is subscribed to the channel, False otherwise
        """
        try:
            # Get channel info using SDK
            channel_info = await self._get_channel_info_sdk(channel_name)
            if not channel_info:
                logger.warning(
                    f"Channel {channel_name} not found or has no subscribers"
                )
                return False

            # For presence channels, check user list for exact user match using SDK
            if channel_name.startswith("presence-"):
                try:
                    users = await self._get_channel_users_sdk(channel_name)

                    if users:
                        is_subscribed = any(user.get("id") == user_id for user in users)
                        return is_subscribed
                    else:
                        return False

                except Exception as e:
                    logger.error(f"Failed to get users for {channel_name}: {e}")
                    return False

            # For private channels, only check if user is subscribed to their OWN channel
            elif channel_name.startswith("private-"):
                # Extract expected user ID from channel name
                if channel_name.startswith("private-user-"):
                    expected_user_id = channel_name.replace("private-user-", "")
                elif channel_name.startswith("private-agent-"):
                    expected_user_id = channel_name.replace("private-agent-", "")
                else:
                    logger.warning(f"Unknown private channel format: {channel_name}")
                    return False

                # Only allow checking if the user is subscribed to their own channel
                if user_id != expected_user_id:
                    logger.warning(
                        f"User {user_id} trying to check subscription to {channel_name} (not their own channel) - returning False"
                    )
                    return False

                # Check if their own channel has any subscribers (should be just them)
                subscriber_count = channel_info.get("subscription_count", 0)
                is_subscribed = subscriber_count > 0
                logger.info(
                    f"Private channel {channel_name}: user {user_id} {'is' if is_subscribed else 'is not'} subscribed (count: {subscriber_count})"
                )
                return is_subscribed

            else:
                logger.warning(
                    f"Unsupported channel type: {channel_name} - returning False"
                )
                return False

        except Exception as e:
            logger.error(f"Error checking channel subscription: {e}")
            return False

    async def is_user_online_in_private_channel(self, user_id: str) -> bool:
        """
        Check if user is online by checking their private-user channel.

        Args:
            user_id: User ID to check

        Returns:
            True if user is connected to their private channel
        """
        channel_name = f"private-user-{user_id}"
        return await self.is_channel_occupied(channel_name)

    async def is_agent_online_in_private_channel(self, agent_id: str) -> bool:
        """
        Check if agent is online by checking their private-agent channel.

        Args:
            agent_id: Agent ID to check

        Returns:
            True if agent is connected to their private channel
        """
        channel_name = f"private-agent-{agent_id}"
        return await self.is_channel_occupied(channel_name)

    async def is_channel_occupied(self, channel_name: str) -> bool:
        """
        Check if a channel has any subscribers.

        Args:
            channel_name: Name of the channel to check

        Returns:
            True if channel has subscribers, False otherwise
        """
        try:
            channel_info = await self._get_channel_info_sdk(channel_name)

            if not channel_info:
                return False

            subscriber_count = channel_info.get("subscription_count", 0)
            return subscriber_count > 0

        except Exception as e:
            logger.error(f"Error checking if channel is occupied: {e}")
            return False

    async def get_chatroom_subscribers(self, chatroom_id: str) -> List[Dict]:
        """
        Get subscribers of a chatroom channel.

        Args:
            chatroom_id: Chatroom ID

        Returns:
            List of subscriber information
        """
        channel_name = f"presence-chatroom-{chatroom_id}"
        return await self.get_channel_subscribers(channel_name)

    async def get_channel_subscribers(self, channel_name: str) -> List[Dict]:
        """
        Get subscribers of a specific channel.

        Args:
            channel_name: Channel name

        Returns:
            List of subscriber information
        """
        try:
            channel_info = await self._get_channel_info_sdk(channel_name)

            if not channel_info:
                return []

            # For presence channels, return user list
            if channel_name.startswith("presence-"):
                return channel_info.get("users", [])

            # For private channels, we can only return subscription count
            subscriber_count = channel_info.get("subscription_count", 0)
            if subscriber_count > 0:
                return [{"count": subscriber_count}]  # Basic info only

            return []

        except Exception as e:
            logger.error(f"Error getting channel subscribers: {e}")
            return []

    async def _get_channel_users_sdk(self, channel_name: str) -> List[Dict]:
        """Get users from a presence channel using the Pusher SDK."""
        try:
            result = pusher_client.channel_users(channel_name)

            if isinstance(result, dict):
                return result.get("users", [])
            else:
                logger.warning(
                    f"Unexpected result type {type(result)} from channel_users"
                )
                return []

        except Exception as e:
            logger.error(f"Error getting channel users via SDK: {e}")
            return []

    async def _get_channel_info_sdk(self, channel_name: str) -> Optional[Dict]:
        """Get channel information using the Pusher SDK."""
        try:
            # For presence channels, include users in the info request
            if channel_name.startswith("presence-"):
                info = "user_count,subscription_count,users"
            else:
                info = "user_count,subscription_count"

            return pusher_client.channel_info(channel_name, info=info)

        except Exception as e:
            logger.error(f"Error getting channel info via SDK: {e}")
            return None

    async def trigger_external_push_notification(
        self, user_id: str, message_data: Dict
    ) -> bool:
        """
        Trigger external push notifications when user is completely offline.

        Args:
            user_id: User ID to notify
            message_data: Message data for the notification

        Returns:
            True if notification was triggered successfully
        """
        try:
            # Handle different message types
            message_type = message_data.get("type", "message")

            if message_type == "message":
                # This is a chatroom message notification
                return await self._send_telegram_chatroom_notification(
                    user_id, message_data
                )
            else:
                # Handle other notification types
                logger.info(
                    f"External push notification type '{message_type}' not yet implemented",
                    extra={
                        "user_id": user_id,
                        "message_type": message_type,
                    },
                )
                return False

        except Exception as e:
            logger.error(f"Error triggering external push notification: {e}")
            return False

    async def _send_telegram_chatroom_notification(
        self, user_id: str, message_data: Dict
    ) -> bool:
        """Send Telegram notification for chatroom message."""
        try:
            if not self.telegram_service.is_available():
                logger.debug("Telegram notification service not available")
                return False

            # Get user's telegram_id using injected dependencies
            user = await self.user_repository.get_by_id(user_id)

            if not user or not user.telegram_id:
                logger.debug(
                    f"User {user_id} has no telegram_id - cannot send Telegram notification",
                    extra={
                        "user_id": user_id,
                        "has_telegram_id": bool(user.telegram_id) if user else False,
                    },
                )
                return False

            # Extract message information
            chatroom_id = message_data.get("chatroom_id", "unknown")
            sender_name = message_data.get("sender_name", "Someone")
            message_text = message_data.get("message", "New message")

            # Send Telegram notification
            success = await self.telegram_service.send_chatroom_notification(
                user_telegram_id=user.telegram_id,
                sender_name=sender_name,
                message_preview=message_text,
                chatroom_id=chatroom_id,
            )

            if success:
                logger.info(
                    "Telegram notification sent via external push",
                    extra={
                        "user_id": user_id,
                        "user_telegram_id": user.telegram_id,
                        "chatroom_id": chatroom_id,
                        "sender_name": sender_name,
                    },
                )

            return success

        except Exception as e:
            logger.error(f"Error sending Telegram chatroom notification: {e}")
            return False


# Global instance
pusher_presence_service = PusherPresenceService()
