"""Notification service for handling real-time notifications via Pusher."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.domain.services.presence_service import pusher_presence_service
from app.integrations.pusher.client import pusher_client

logger = get_logger(__name__)


class NotificationService:
    """Service for managing real-time notifications through Pusher with presence awareness."""

    def __init__(self) -> None:
        """Initialize notification service."""
        self.pusher_client = None
        self.presence_service = pusher_presence_service
        self._notification_cache: Dict[str, datetime] = {}  # For duplicate suppression
        self._initialize_pusher_client()

    def _initialize_pusher_client(self) -> None:
        """Initialize Pusher client lazily to avoid circular imports."""
        try:
            self.pusher_client = pusher_client
            logger.debug("Pusher client initialized for notification service")
        except ImportError as e:
            logger.error(f"Failed to initialize Pusher client: {e}")
            self.pusher_client = None

    def _should_suppress_notification(
        self, user_id: str, notification_type: str, ttl_minutes: int = 5
    ) -> bool:
        """Check if notification should be suppressed due to recent duplicate."""
        cache_key = f"{user_id}:{notification_type}"
        current_time = datetime.now(timezone.utc)

        if cache_key in self._notification_cache:
            time_diff = current_time - self._notification_cache[cache_key]
            if time_diff.total_seconds() < (ttl_minutes * 60):
                logger.debug(f"Suppressing duplicate notification: {cache_key}")
                return True

        # Update cache
        self._notification_cache[cache_key] = current_time
        return False

    def _cleanup_notification_cache(self, max_age_minutes: int = 30) -> None:
        """Clean up old entries from notification cache."""
        current_time = datetime.now(timezone.utc)
        expired_keys = []

        for key, timestamp in self._notification_cache.items():
            age_minutes = (current_time - timestamp).total_seconds() / 60
            if age_minutes > max_age_minutes:
                expired_keys.append(key)

        for key in expired_keys:
            del self._notification_cache[key]

    async def send_message_with_presence_routing(
        self,
        recipient_id: str,
        recipient_type: str,  # "user" or "agent"
        chatroom_id: str,
        message_data: Dict[str, Any],
        sender_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send message using Pusher presence-aware routing.

        Logic:
        1. Check if recipient is subscribed to chatroom channel via Pusher presence API
        2. If subscribed → send message directly to presence-chatroom-{chatroom_id}
        3. If online (in private channel) but not subscribed → send notify to private-{type}-{id}
        4. If not online at all → trigger external push (Telegram, FCM, etc.)

        Args:
            recipient_id: Target recipient ID (user_id or agent_id)
            recipient_type: Type of recipient ("user" or "agent")
            chatroom_id: Chatroom ID for message routing
            message_data: Message content and metadata
            sender_info: Sender information (agent/user data)

        Returns:
            Dict with routing decision and delivery status
        """
        if not self.pusher_client:
            logger.error("Pusher client not available for message routing")
            raise Exception("Notification service not available")

        current_time = datetime.now(timezone.utc).isoformat()
        chatroom_channel = f"presence-chatroom-{chatroom_id}"

        # Step 1: Check if recipient is subscribed to the chatroom channel
        is_subscribed_to_chatroom = (
            await self.presence_service.is_user_subscribed_to_channel(
                chatroom_channel, recipient_id
            )
        )

        if is_subscribed_to_chatroom:
            # Recipient is subscribed to chatroom - send message directly
            try:
                self.pusher_client.trigger(
                    chatroom_channel,
                    "message.new",
                    {
                        **message_data,
                        "timestamp": current_time,
                        "sender": sender_info,
                        "routing": "direct_to_chatroom",
                    },
                )

                logger.info(
                    "Message sent directly to chatroom",
                    extra={
                        "recipient_id": recipient_id,
                        "recipient_type": recipient_type,
                        "chatroom_id": chatroom_id,
                        "channel": chatroom_channel,
                        "routing": "direct_to_chatroom",
                    },
                )

                return {
                    "message_sent": True,
                    "routing": "direct_to_chatroom",
                    "channel": chatroom_channel,
                    "recipient_subscribed": True,
                    "timestamp": current_time,
                }

            except Exception as e:
                logger.error(f"Failed to send direct message to chatroom: {e}")
                raise Exception(f"Failed to send direct message: {str(e)}")

        # Step 2: Recipient not subscribed to chatroom - check if they're online in their private channel
        if recipient_type == "user":
            is_online = await self.presence_service.is_user_online_in_private_channel(
                recipient_id
            )
            private_channel = f"private-user-{recipient_id}"
        elif recipient_type == "agent":
            is_online = await self.presence_service.is_agent_online_in_private_channel(
                recipient_id
            )
            private_channel = f"private-agent-{recipient_id}"
        else:
            raise ValueError(
                f"Invalid recipient_type: {recipient_type}. Must be 'user' or 'agent'"
            )

        if is_online:
            # Recipient is online but not subscribed to chatroom - send notify to private channel
            if self._should_suppress_notification(recipient_id, "message.notify"):
                logger.debug(
                    f"Suppressing duplicate notification for {recipient_type} {recipient_id}"
                )
                return {
                    "message_sent": False,
                    "routing": "suppressed",
                    "recipient_online": True,
                    "recipient_subscribed": False,
                    "reason": "duplicate_notification_suppressed",
                }

            notify_data = {
                "type": "message.notify",
                "chatroom_id": chatroom_id,
                "sender": sender_info,
                "timestamp": current_time,
                "action_required": "re_auth_and_subscribe_to_chatroom",
                "chatroom_channel": chatroom_channel,
                "message_preview": message_data.get("message", "")[
                    :100
                ],  # First 100 chars
            }

            try:
                self.pusher_client.trigger(
                    private_channel, "message.notify", notify_data
                )

                logger.info(
                    f"Notify sent to online {recipient_type}'s private channel",
                    extra={
                        "recipient_id": recipient_id,
                        "recipient_type": recipient_type,
                        "chatroom_id": chatroom_id,
                        "channel": private_channel,
                        "routing": "notify_to_private",
                    },
                )

                return {
                    "message_sent": True,
                    "routing": "notify_to_private",
                    "channel": private_channel,
                    "recipient_online": True,
                    "recipient_subscribed": False,
                    "timestamp": current_time,
                }

            except Exception as e:
                logger.error(f"Failed to send notify to private channel: {e}")
                raise Exception(f"Failed to send notification: {str(e)}")

        else:
            # Step 3: Recipient is completely offline - trigger external push notifications
            external_push_data = {
                "type": "message",
                "recipient_type": recipient_type,
                "chatroom_id": chatroom_id,
                "sender_id": sender_info.get("user_id") or sender_info.get("agent_id"),
                "sender_name": sender_info.get("name") or sender_info.get("agent_name"),
                "message": message_data.get("message", ""),
                "timestamp": current_time,
            }

            try:
                external_success = (
                    await self.presence_service.trigger_external_push_notification(
                        recipient_id, external_push_data
                    )
                )

                logger.info(
                    f"External push notification triggered for offline {recipient_type}",
                    extra={
                        "recipient_id": recipient_id,
                        "recipient_type": recipient_type,
                        "chatroom_id": chatroom_id,
                        "routing": "external_push",
                        "success": external_success,
                    },
                )

                return {
                    "message_sent": external_success,
                    "routing": "external_push",
                    "recipient_online": False,
                    "recipient_subscribed": False,
                    "external_push_triggered": external_success,
                    "timestamp": current_time,
                }

            except Exception as e:
                logger.error(f"Failed to trigger external push notification: {e}")
                return {
                    "message_sent": False,
                    "routing": "external_push_failed",
                    "recipient_online": False,
                    "recipient_subscribed": False,
                    "error": str(e),
                    "timestamp": current_time,
                }

    async def send_user_notification(
        self,
        user_id: str,
        notification_type: str,
        message: str,
        sender_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        suppress_duplicates: bool = True,
    ) -> Dict[str, Any]:
        """
        Send notification to user's private-user channel with presence awareness.
        """
        return await self.send_private_channel_notification(
            recipient_id=user_id,
            recipient_type="user",
            notification_type=notification_type,
            message=message,
            sender_data=sender_data,
            metadata=metadata,
            suppress_duplicates=suppress_duplicates,
        )

    async def send_agent_notification(
        self,
        agent_id: str,
        notification_type: str,
        message: str,
        sender_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        suppress_duplicates: bool = True,
    ) -> Dict[str, Any]:
        """
        Send notification to agent's private-agent channel with presence awareness.
        """
        return await self.send_private_channel_notification(
            recipient_id=agent_id,
            recipient_type="agent",
            notification_type=notification_type,
            message=message,
            sender_data=sender_data,
            metadata=metadata,
            suppress_duplicates=suppress_duplicates,
        )

    async def send_private_channel_notification(
        self,
        recipient_id: str,
        recipient_type: str,  # "user" or "agent"
        notification_type: str,
        message: str,
        sender_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        suppress_duplicates: bool = True,
    ) -> Dict[str, Any]:
        """
        Send notification to recipient's private channel with presence awareness.

        Args:
            recipient_id: Target recipient ID (user_id or agent_id)
            recipient_type: Type of recipient ("user" or "agent")
            notification_type: Type of notification (e.g., 'agent.wants_chat', 'agent.message')
            message: Notification message content
            sender_data: Information about the sender (agent, etc.)
            metadata: Additional metadata for the notification
            suppress_duplicates: Whether to suppress duplicate notifications

        Returns:
            Dict with notification delivery status and details

        Raises:
            Exception: If Pusher client is not available or notification fails
        """
        if not self.pusher_client:
            logger.error("Pusher client not available for notification")
            raise Exception("Notification service not available")

        # Check for duplicate suppression
        if suppress_duplicates and self._should_suppress_notification(
            recipient_id, notification_type
        ):
            logger.debug(
                f"Suppressing duplicate notification: {recipient_id}:{notification_type}"
            )
            return {
                "notification_sent": False,
                "reason": "duplicate_suppressed",
                "recipient_id": recipient_id,
                "recipient_type": recipient_type,
                "notification_type": notification_type,
            }

        # Clean up old cache entries periodically
        if len(self._notification_cache) > 1000:  # Arbitrary threshold
            self._cleanup_notification_cache()

        # Check recipient presence
        if recipient_type == "user":
            is_online = await self.presence_service.is_user_online_in_private_channel(
                recipient_id
            )
            channel_name = f"private-user-{recipient_id}"
        elif recipient_type == "agent":
            is_online = await self.presence_service.is_agent_online_in_private_channel(
                recipient_id
            )
            channel_name = f"private-agent-{recipient_id}"
        else:
            raise ValueError(
                f"Invalid recipient_type: {recipient_type}. Must be 'user' or 'agent'"
            )

        # Prepare notification payload
        notification_data = {
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            "recipient_online": is_online,
            "recipient_type": recipient_type,
            **sender_data,  # Include all sender data (agent_id, agent_name, etc.)
        }

        try:
            self.pusher_client.trigger(
                channel_name, notification_type, notification_data
            )

            logger.info(
                f"{recipient_type.capitalize()} notification sent successfully",
                extra={
                    "recipient_id": recipient_id,
                    "recipient_type": recipient_type,
                    "notification_type": notification_type,
                    "channel": channel_name,
                    "recipient_online": is_online,
                    "sender_id": sender_data.get("agent_id")
                    or sender_data.get("user_id"),
                },
            )

            return {
                "notification_sent": True,
                "channel": channel_name,
                "event": notification_type,
                "target_recipient_id": recipient_id,
                "recipient_type": recipient_type,
                "recipient_online": is_online,
                "timestamp": notification_data["timestamp"],
            }

        except Exception as e:
            logger.error(
                f"Failed to send {recipient_type} notification",
                extra={
                    "recipient_id": recipient_id,
                    "recipient_type": recipient_type,
                    "notification_type": notification_type,
                    "error": str(e),
                },
            )
            raise Exception(f"Failed to send notification: {str(e)}")

    async def send_agent_chat_request(
        self,
        user_id: str,
        agent_data: Dict[str, Any],
        message: str,
        sub_account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send agent chat request notification to user.

        Args:
            user_id: Target user ID
            agent_data: Agent information (id, name, display_name, etc.)
            message: Chat request message
            sub_account_id: Optional sub-account ID

        Returns:
            Dict with notification delivery status
        """
        sender_data = {
            "agent_id": agent_data.get("id") or agent_data.get("agent_id"),
            "agent_name": agent_data.get("name"),
            "agent_display_name": agent_data.get("display_name")
            or agent_data.get("name"),
            "sub_account_id": sub_account_id or agent_data.get("id"),
        }

        return await self.send_user_notification(
            user_id=user_id,
            notification_type="agent.wants_chat",
            message=message,
            sender_data=sender_data,
            metadata={"chat_request": True, "requires_response": True},
        )

    async def send_agent_message_notification(
        self,
        user_id: str,
        agent_data: Dict[str, Any],
        message: str,
        chatroom_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send agent message notification to user.

        Args:
            user_id: Target user ID
            agent_data: Agent information
            message: Message content
            chatroom_id: Optional chatroom ID

        Returns:
            Dict with notification delivery status
        """
        sender_data = {
            "agent_id": agent_data.get("id") or agent_data.get("agent_id"),
            "agent_name": agent_data.get("name"),
            "agent_display_name": agent_data.get("display_name")
            or agent_data.get("name"),
        }

        return await self.send_user_notification(
            user_id=user_id,
            notification_type="agent.message",
            message=message,
            sender_data=sender_data,
            metadata={"chatroom_id": chatroom_id, "message_type": "direct"},
        )

    async def send_general_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        sender_type: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send general notification to user.

        Args:
            user_id: Target user ID
            title: Notification title
            message: Notification message
            sender_type: Type of sender (system, admin, etc.)
            metadata: Additional metadata

        Returns:
            Dict with notification delivery status
        """
        sender_data = {"sender_type": sender_type, "title": title}

        return await self.send_user_notification(
            user_id=user_id,
            notification_type="notification",
            message=message,
            sender_data=sender_data,
            metadata=metadata or {},
        )

    async def send_match_notification(
        self, user_id: str, match_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send match created notification to user.

        Args:
            user_id: Target user ID
            match_data: Match information including peer data and conversation details

        Returns:
            Dict with notification delivery status
        """
        sender_data = {
            "match_id": match_data.get("id"),
            "conversation_id": match_data.get("conversation_id"),
            "peer": match_data.get("peer", {}),
            "created_at": match_data.get("created_at"),
        }

        peer_name = match_data.get("peer", {}).get("display_name") or "Someone"
        message = f"You have a new match with {peer_name}!"

        return await self.send_user_notification(
            user_id=user_id,
            notification_type="match.created",
            message=message,
            sender_data=sender_data,
            metadata={"match_created": True, "requires_response": True},
        )

    def is_available(self) -> bool:
        """Check if notification service is available."""
        return self.pusher_client is not None
