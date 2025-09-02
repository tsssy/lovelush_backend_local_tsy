"""Workflow manager for handling workflow states."""

from datetime import datetime, timedelta
from typing import Dict, Optional, Type

from app.core.logging import get_logger
from app.infrastructure.database.repositories.workflow_repository import (
    WorkflowRepository,
)
from app.interfaces.telegram.common.types import TelegramMessage, TelegramUser
from app.interfaces.telegram.models.workflow import WorkflowStateCreate, WorkflowStep

from .workflows.base_workflow import TelegramBaseWorkflow, TelegramWorkflowResponse

logger = get_logger(__name__)


class TelegramWorkflowManager:
    """Manages workflow states and lifecycle using database storage."""

    def __init__(self) -> None:
        self._workflow_classes: Dict[str, Type[TelegramBaseWorkflow]] = {}
        self._default_timeout = timedelta(hours=1)
        self._repository = WorkflowRepository()

    def register_workflow(
        self, workflow_type: str, workflow_class: Type[TelegramBaseWorkflow]
    ) -> None:
        """Register a workflow class."""
        self._workflow_classes[workflow_type] = workflow_class
        logger.info(f"Registered workflow: {workflow_type}")

    def _get_user_key(self, user_id: int, chat_id: int) -> str:
        """Get unique key for user workflow - kept for compatibility."""
        return f"{user_id}:{chat_id}"

    async def has_active_workflow(self, telegram_user_id: int, chat_id: int) -> bool:
        """Check if user has active workflow (not expired or completed)."""
        workflow_state = await self._repository.get_by_user_and_chat(
            telegram_user_id, chat_id
        )
        if not workflow_state:
            return False

        # Check if workflow is completed
        if workflow_state.current_step == WorkflowStep.COMPLETE:
            return False

        # Check if workflow is expired
        if workflow_state.expires_at and workflow_state.expires_at < datetime.now():
            await self.cancel_workflow(telegram_user_id, chat_id)
            return False

        return True

    async def get_active_workflow(
        self, telegram_user_id: int, chat_id: int
    ) -> Optional[TelegramBaseWorkflow]:
        """Get active workflow for telegram user."""
        if not await self.has_active_workflow(telegram_user_id, chat_id):
            return None

        workflow_state = await self._repository.get_by_user_and_chat(
            telegram_user_id, chat_id
        )
        if not workflow_state:
            return None

        workflow_class = self._workflow_classes.get(workflow_state.workflow_type)
        if not workflow_class:
            return None

        return workflow_class(workflow_state)

    async def start_workflow(
        self,
        workflow_type: str,
        user_id: str,
        telegram_user_id: int,
        chat_id: int,
        timeout: Optional[timedelta] = None,
    ) -> Optional[TelegramWorkflowResponse]:
        """Start a new workflow."""
        if workflow_type not in self._workflow_classes:
            logger.error(f"Unknown workflow type: {workflow_type}")
            return None

        if await self.has_active_workflow(telegram_user_id, chat_id):
            logger.warning(
                f"Telegram user {telegram_user_id} already has active workflow"
            )
            return None

        now = datetime.now()
        expires_at = now + (timeout or self._default_timeout)

        # Determine starting step based on workflow type
        starting_step = WorkflowStep.GENDER  # Default for onboarding/restart
        if workflow_type == "products":
            starting_step = WorkflowStep.PRODUCTS_LIST

        # Create workflow state in database
        workflow_data = WorkflowStateCreate(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            workflow_type=workflow_type,
            current_step=starting_step,
            expires_at=expires_at,
            last_message_id=None,
        )

        workflow_state = await self._repository.create(workflow_data)

        workflow_class = self._workflow_classes[workflow_type]
        workflow = workflow_class(workflow_state)

        logger.info(
            f"Started {workflow_type} workflow for telegram user {telegram_user_id}"
        )
        return await workflow.start()

    async def process_message(
        self, message: TelegramMessage
    ) -> Optional[TelegramWorkflowResponse]:
        """Process message for active workflow."""
        if not message.from_user:
            return None

        workflow = await self.get_active_workflow(message.from_user.id, message.chat.id)
        if not workflow:
            return None

        response = await workflow.process_message(message)

        # Update database if workflow completed
        if workflow.state.current_step == WorkflowStep.COMPLETE:
            await self.complete_workflow(message.from_user.id, message.chat.id)

        return response

    async def process_callback_query(
        self, callback_data: str, user: TelegramUser, chat_id: int
    ) -> Optional[TelegramWorkflowResponse]:
        """Process callback query for active workflow."""
        workflow = await self.get_active_workflow(user.id, chat_id)
        if not workflow:
            return None

        response = await workflow.process_callback_query(callback_data, user)

        # Update database if workflow completed
        if workflow.state.current_step == WorkflowStep.COMPLETE:
            await self.complete_workflow(user.id, chat_id)

        return response

    async def cancel_workflow(self, user_id: int, chat_id: int) -> bool:
        """Cancel active workflow."""
        result = await self._repository.delete_by_user_and_chat(user_id, chat_id)
        if result:
            logger.info(f"Cancelled workflow for user {user_id}")
        return result

    async def complete_workflow(self, user_id: int, chat_id: int) -> bool:
        """Mark workflow as completed but preserve for analysis."""
        # Update workflow state to mark as completed instead of deleting
        workflow_state = await self._repository.get_by_user_and_chat(user_id, chat_id)
        if not workflow_state:
            return False

        # Update with completion timestamp for analysis
        workflow_state.data["completed_at"] = datetime.now().isoformat()
        workflow_state.data["status"] = "completed"

        # Update the workflow state in database instead of deleting
        result = await self._repository.update_step_and_data(
            user_id, chat_id, WorkflowStep.COMPLETE, workflow_state.data
        )

        if result:
            logger.info(f"Completed workflow for user {user_id}: {workflow_state.data}")
            return True
        return False

    async def cleanup_expired_workflows(self) -> int:
        """Remove expired workflows."""
        count = await self._repository.cleanup_expired_workflows()
        if count > 0:
            logger.info(f"Cleaned up {count} expired workflows")
        return count

    async def get_completed_workflows(self, limit: Optional[int] = None) -> list:
        """Get completed workflows for analysis."""
        return await self._repository.get_completed_workflows(limit)

    async def get_user_workflow_history(self, user_id: int) -> list:
        """Get all workflows for a specific user."""
        return await self._repository.get_user_workflow_history(user_id)

    async def get_workflow_analytics(self):
        """Get workflow analytics data."""
        completed_workflows = await self._repository.get_completed_workflows()

        analytics = {
            "total_completed": len(completed_workflows),
            "completion_rate": 0,
            "average_completion_time": 0,
            "step_drop_off": {},
            "most_common_selections": {"gender": {}, "age_ranges": {}, "locations": {}},
        }

        if completed_workflows:
            # Analyze completion data
            total_time = 0
            gender_count = {}
            location_count = {}

            for workflow in completed_workflows:
                # Calculate completion time if available
                if workflow.created_at and "completed_at" in workflow.data:
                    try:
                        completed_at = datetime.fromisoformat(
                            workflow.data["completed_at"]
                        )
                        completion_time = (
                            completed_at - workflow.created_at
                        ).total_seconds()
                        total_time += completion_time
                    except:
                        pass

                # Count gender selections
                if "gender" in workflow.data:
                    gender = workflow.data["gender"]
                    gender_count[gender] = gender_count.get(gender, 0) + 1

                # Count location selections
                if "location" in workflow.data:
                    location = workflow.data["location"]
                    location_count[location] = location_count.get(location, 0) + 1

            # Calculate averages
            if total_time > 0:
                analytics["average_completion_time"] = total_time / len(
                    completed_workflows
                )

            analytics["most_common_selections"]["gender"] = gender_count
            analytics["most_common_selections"]["locations"] = location_count

        return analytics


telegram_workflow_manager = TelegramWorkflowManager()
