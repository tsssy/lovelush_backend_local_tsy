"""
Centralized dependency injection container following CLAUDE.md standards.
Manages all service and repository instances in a single location.
"""

from typing import Any, Dict

from app.domain.services.agent_service import AgentService
from app.domain.services.app_settings_service import AppSettingsService
from app.domain.services.chatroom_service import ChatroomService
from app.domain.services.credits_service import CreditsService
from app.domain.services.matching_service import MatchingService
from app.domain.services.message_credit_service import MessageCreditService
from app.domain.services.notification_service import NotificationService
from app.domain.services.payment_service import PaymentService
from app.domain.services.presence_service import PusherPresenceService
from app.domain.services.product_service import ProductService
from app.domain.services.upload_service import UploadService
from app.domain.services.user_service import UserService
from app.infrastructure.database.repositories.agent_repository import (
    AgentRepository,
    SubAccountRepository,
)
from app.infrastructure.database.repositories.app_settings_repository import (
    AppSettingsRepository,
)
from app.infrastructure.database.repositories.bot_message_repository import (
    BotMessageRepository,
)
from app.infrastructure.database.repositories.chatroom_repository import (
    ChatroomRepository,
)
from app.infrastructure.database.repositories.credit_transaction_repository import (
    CreditTransactionRepository,
)
from app.infrastructure.database.repositories.credits_repository import (
    CreditsRepository,
)
from app.infrastructure.database.repositories.match_repository import (
    MatchRecordRepository,
)
from app.infrastructure.database.repositories.message_repository import (
    MessageRepository,
)
from app.infrastructure.database.repositories.payment_repository import (
    PaymentRepository,
)
from app.infrastructure.database.repositories.product_repository import (
    ProductRepository,
)
from app.infrastructure.database.repositories.user_message_stats_repository import (
    UserMessageStatsRepository,
)
from app.infrastructure.database.repositories.user_repository import UserRepository
from app.infrastructure.database.repositories.workflow_repository import (
    WorkflowRepository,
)
from app.integrations.pusher.chatroom_service import ChatroomPusherService
from app.interfaces.telegram.services.bot_message_service import BotMessageService
from app.interfaces.telegram.services.notification_service import (
    TelegramNotificationService,
)
from app.interfaces.telegram.services.sdk_service import TelegramSDKService


class DependencyContainer:
    """
    Centralized dependency injection container.

    Manages all service and repository instances as singletons.
    Ensures proper dependency injection following clean architecture.
    Uses lazy loading to avoid database initialization issues.
    """

    def __init__(self):
        """Initialize the container with lazy loading."""
        self._repositories: Dict[str, Any] = {}
        self._services: Dict[str, Any] = {}
        self._repository_classes = {
            "agent": AgentRepository,
            "app_settings": AppSettingsRepository,
            "sub_account": SubAccountRepository,
            "bot_message": BotMessageRepository,
            "chatroom": ChatroomRepository,
            "credits": CreditsRepository,
            "credit_transaction": CreditTransactionRepository,
            "match_record": MatchRecordRepository,
            "message": MessageRepository,
            "payment": PaymentRepository,
            "product": ProductRepository,
            "user": UserRepository,
            "user_message_stats": UserMessageStatsRepository,
            "workflow": WorkflowRepository,
        }

    def _get_repository(self, repo_name: str) -> Any:
        """Lazy-load repository instance."""
        if repo_name not in self._repositories:
            repo_class = self._repository_classes.get(repo_name)
            if repo_class is None:
                raise KeyError(f"Repository class '{repo_name}' not found")

            # Special case for CreditsRepository that needs dependency injection
            if repo_name == "credits":
                # Create the transaction repository first
                transaction_repo = self._get_repository("credit_transaction")
                # Create credits repository with transaction repository injected
                credits_repo = repo_class(
                    credit_transaction_repository=transaction_repo
                )
                self._repositories[repo_name] = credits_repo
            else:
                self._repositories[repo_name] = repo_class()

        return self._repositories[repo_name]

    def _get_service(self, service_name: str) -> Any:
        """Lazy-load service instance with dependencies."""
        if service_name not in self._services:
            if service_name == "agent":
                self._services[service_name] = AgentService(
                    self._get_repository("agent"), self._get_repository("sub_account")
                )
            elif service_name == "app_settings":
                self._services[service_name] = AppSettingsService(
                    self._get_repository("app_settings")
                )
            elif service_name == "bot_message":
                self._services[service_name] = BotMessageService(
                    self._get_repository("bot_message")
                )
            elif service_name == "chatroom":
                self._services[service_name] = ChatroomService(
                    self._get_repository("chatroom"),
                    self._get_repository("agent"),
                    self._get_repository("user"),
                    self._get_repository("message"),
                    self._get_service("notification"),
                    self._get_service("chatroom_pusher"),
                    self._get_service("pusher_presence"),
                    self._get_service("message_credit"),
                )
            elif service_name == "credits":
                self._services[service_name] = CreditsService(
                    self._get_repository("credits"),
                    self._get_service("app_settings"),
                )
            elif service_name == "product":
                self._services[service_name] = ProductService(
                    self._get_repository("product")
                )
            elif service_name == "user":
                self._services[service_name] = UserService(self._get_repository("user"))
            elif service_name == "upload":
                self._services[service_name] = UploadService(
                    self._get_repository("sub_account")
                )
            elif service_name == "payment":
                self._services[service_name] = PaymentService(
                    self._get_repository("payment"),
                    self._get_repository("product"),
                    self._get_service("credits"),
                    self._get_service("user"),
                    self._get_service("telegram_sdk"),
                )
            elif service_name == "matching":
                self._services[service_name] = MatchingService(
                    self._get_repository("agent"),
                    self._get_repository("chatroom"),
                    self._get_service("credits"),
                    self._get_repository("match_record"),
                    self._get_service("chatroom_pusher"),
                    self._get_service("app_settings"),
                )
            elif service_name == "message_credit":
                self._services[service_name] = MessageCreditService(
                    self._get_service("credits"),
                    self._get_service("app_settings"),
                    self._get_repository("user_message_stats"),
                )
            elif service_name == "notification":
                self._services[service_name] = NotificationService()
            elif service_name == "chatroom_pusher":
                self._services[service_name] = ChatroomPusherService()
            elif service_name == "pusher_presence":
                self._services[service_name] = PusherPresenceService(
                    user_repository=self._get_repository("user")
                )
            elif service_name == "telegram_sdk":
                self._services[service_name] = TelegramSDKService()
            elif service_name == "telegram_notification":
                self._services[service_name] = TelegramNotificationService()
            else:
                raise KeyError(f"Service '{service_name}' not found")

        return self._services[service_name]

    def get_service(self, service_name: str) -> Any:
        """
        Get service instance by name.

        Args:
            service_name: Name of the service to retrieve

        Returns:
            Service instance

        Raises:
            KeyError: If service name not found
        """
        return self._get_service(service_name)

    def get_repository(self, repo_name: str) -> Any:
        """
        Get repository instance by name.

        Args:
            repo_name: Name of the repository to retrieve

        Returns:
            Repository instance

        Raises:
            KeyError: If repository name not found
        """
        return self._get_repository(repo_name)

    def list_services(self) -> list[str]:
        """Get list of all available service names."""
        return [
            "agent",
            "app_settings",
            "bot_message",
            "chatroom",
            "chatroom_pusher",
            "credits",
            "matching",
            "message_credit",
            "notification",
            "payment",
            "product",
            "pusher_presence",
            "telegram_notification",
            "telegram_sdk",
            "upload",
            "user",
        ]

    def list_repositories(self) -> list[str]:
        """Get list of all available repository names."""
        return list(self._repository_classes.keys())


# Global container instance - singleton pattern
_container: DependencyContainer | None = None


def get_container() -> DependencyContainer:
    """
    Get the global dependency container instance.

    Uses singleton pattern to ensure only one container exists.

    Returns:
        DependencyContainer: Global container instance
    """
    global _container
    if _container is None:
        _container = DependencyContainer()
    return _container


# FastAPI dependency functions
def get_agent_service() -> AgentService:
    """Get AgentService instance from container."""
    return get_container().get_service("agent")


def get_app_settings_service() -> AppSettingsService:
    """Get AppSettingsService instance from container."""
    return get_container().get_service("app_settings")


def get_bot_message_service() -> BotMessageService:
    """Get BotMessageService instance from container."""
    return get_container().get_service("bot_message")


def get_chatroom_service() -> ChatroomService:
    """Get ChatroomService instance from container."""
    return get_container().get_service("chatroom")


def get_credits_service() -> CreditsService:
    """Get CreditsService instance from container."""
    return get_container().get_service("credits")


def get_message_credit_service() -> MessageCreditService:
    """Get MessageCreditService instance from container."""
    return get_container().get_service("message_credit")


def get_matching_service() -> MatchingService:
    """Get MatchingService instance from container."""
    return get_container().get_service("matching")


def get_payment_service() -> PaymentService:
    """Get PaymentService instance from container."""
    return get_container().get_service("payment")


def get_product_service() -> ProductService:
    """Get ProductService instance from container."""
    return get_container().get_service("product")


def get_user_service() -> UserService:
    """Get UserService instance from container."""
    return get_container().get_service("user")


def get_upload_service() -> UploadService:
    """Get UploadService instance from container."""
    return get_container().get_service("upload")


def get_notification_service() -> NotificationService:
    """Get NotificationService instance from container."""
    return get_container().get_service("notification")


def get_telegram_notification_service():
    """Get TelegramNotificationService instance from container."""
    return get_container().get_service("telegram_notification")


def get_telegram_sdk_service():
    """Get TelegramSDKService instance from container."""
    return get_container().get_service("telegram_sdk")


def get_credit_transaction_repository():
    """Get CreditTransactionRepository instance from container."""
    return get_container().get_repository("credit_transaction")
