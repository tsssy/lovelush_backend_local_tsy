"""Enhanced onboarding workflow using new infrastructure."""

from typing import Optional

from app.core.logging import get_logger
from app.interfaces.telegram.common.types import TelegramMessage, TelegramUser
from app.interfaces.telegram.models.workflow import WorkflowState
from app.interfaces.telegram.workflows.base_workflow import TelegramWorkflowResponse

from .enhanced_workflow import TelegramEnhancedWorkflow

logger = get_logger(__name__)


class TelegramOnboardingWorkflow(TelegramEnhancedWorkflow):
    """Enhanced onboarding workflow with step-based architecture."""

    def __init__(self, state: WorkflowState):
        super().__init__(state)
        logger.info("Initialized TelegramOnboardingWorkflow")

    async def process_message(
        self, message: TelegramMessage
    ) -> Optional[TelegramWorkflowResponse]:
        """Process message with enhanced infrastructure."""
        logger.info(
            f"Processing message in step {self.state.current_step}: {message.text}"
        )
        return await super().process_message(message)

    async def process_callback_query(
        self, callback_data: str, user: TelegramUser
    ) -> Optional[TelegramWorkflowResponse]:
        """Process callback query with enhanced infrastructure."""
        logger.info(
            f"Processing callback in step {self.state.current_step}: {callback_data}"
        )
        return await super().process_callback_query(callback_data, user)
