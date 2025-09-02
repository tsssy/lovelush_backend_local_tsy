"""Enhanced Pusher integration for chatroom real-time messaging."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.domain.models.chatroom import ChatroomStatus
from app.integrations.pusher.client import pusher_client

logger = get_logger(__name__)


class ChatroomPusherService:
    """Service for managing Pusher events in chatrooms."""

    def __init__(self) -> None:
        self.pusher_client = pusher_client

    async def send_message_event(
        self,
        channel: str,
        sender_id: str,
        sender_type: str,
        message: str,
        message_type: str = "text",
        metadata: Optional[Dict] = None,
        chatroom_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a message event via Pusher."""
        message_payload = {
            "id": f"msg_{int(datetime.now().timestamp() * 1000)}",
            "chatroom_id": chatroom_id,
            "sender_id": sender_id,
            "sender_type": sender_type,
            "message": message,
            "message_type": message_type,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"Attempting to send Pusher message to channel: {channel}")
        logger.info(f"Pusher client initialized: {self.pusher_client._initialized}")
        logger.info(f"Message payload: {message_payload}")

        try:
            result = self.pusher_client.trigger(channel, "new_message", message_payload)
            logger.info(
                f"Pusher message sent successfully to channel {channel} by {sender_type}:{sender_id}. Result: {result}"
            )
            return message_payload
        except Exception as e:
            logger.error(f"Failed to send message via Pusher: {e}")
            logger.exception("Full Pusher error traceback:")
            raise

    async def send_system_event(
        self,
        channel: str,
        message: str,
        event_type: str = "system_message",
        metadata: Optional[Dict] = None,
        chatroom_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a system event via Pusher."""
        system_payload = {
            "id": f"sys_{int(datetime.now().timestamp() * 1000)}",
            "chatroom_id": chatroom_id,
            "sender_id": "system",
            "sender_type": "system",
            "message": message,
            "message_type": event_type,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            self.pusher_client.trigger(channel, event_type, system_payload)
            logger.info(f"System event {event_type} sent to channel {channel}")
            return system_payload
        except Exception as e:
            logger.error(f"Failed to send system event via Pusher: {e}")
            raise

    async def send_typing_indicator(
        self, channel: str, sender_id: str, is_typing: bool
    ) -> bool:
        """Send typing indicator via Pusher."""
        typing_payload = {
            "sender_id": sender_id,
            "is_typing": is_typing,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            self.pusher_client.trigger(channel, "typing_indicator", typing_payload)
            logger.debug(
                f"Typing indicator sent: {sender_id} is {'typing' if is_typing else 'not typing'}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send typing indicator via Pusher: {e}")
            return False

    async def send_user_joined(
        self, channel: str, user_id: str, user_info: Dict[str, Any]
    ) -> bool:
        """Send user joined event."""
        join_payload = {
            "user_id": user_id,
            "user_info": user_info,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            self.pusher_client.trigger(channel, "user_joined", join_payload)
            logger.info(f"User {user_id} joined channel {channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to send user joined event via Pusher: {e}")
            return False

    async def send_user_left(self, channel: str, user_id: str) -> bool:
        """Send user left event."""
        leave_payload = {
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            self.pusher_client.trigger(channel, "user_left", leave_payload)
            logger.info(f"User {user_id} left channel {channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to send user left event via Pusher: {e}")
            return False

    async def send_chatroom_status_change(
        self, channel: str, status: ChatroomStatus, ended_by: Optional[str] = None
    ) -> bool:
        """Send chatroom status change event."""
        status_payload = {
            "status": status,
            "ended_by": ended_by,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            self.pusher_client.trigger(channel, "status_change", status_payload)
            logger.info(f"Chatroom status changed to {status} in channel {channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to send status change event via Pusher: {e}")
            return False

    async def authenticate_user_for_channel(
        self,
        channel: str,
        socket_id: str,
        user_id: str,
        user_info: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Authenticate user for a private chatroom channel."""
        try:
            # For presence channels, include user info
            if channel.startswith("presence-"):
                custom_data = {"user_id": user_id, "user_info": user_info or {}}
                auth_data = self.pusher_client.authenticate(
                    channel=channel, socket_id=socket_id, custom_data=custom_data
                )
            else:
                auth_data = self.pusher_client.authenticate(
                    channel=channel, socket_id=socket_id
                )

            logger.info(f"User {user_id} authenticated for channel {channel}")
            return auth_data

        except Exception as e:
            logger.error(f"Failed to authenticate user for Pusher channel: {e}")
            raise

    def get_chatroom_channel_name(self, chatroom_id: str, private: bool = True) -> str:
        """Generate standardized channel name for chatroom."""
        prefix = "private-" if private else ""
        return f"{prefix}chatroom-{chatroom_id}"

    def get_presence_channel_name(self, chatroom_id: str) -> str:
        """Generate presence channel name for chatroom."""
        return f"presence-chatroom-{chatroom_id}"


# Global instance
chatroom_pusher_service = ChatroomPusherService()
