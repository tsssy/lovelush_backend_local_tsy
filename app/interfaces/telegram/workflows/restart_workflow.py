"""Restart workflow for updating existing user information."""

from typing import Optional

from app.core.logging import get_logger
from app.interfaces.telegram.common.types import TelegramMessage, TelegramUser
from app.interfaces.telegram.models.workflow import WorkflowState, WorkflowStep
from app.interfaces.telegram.skill.rendering import MessageFormatter, UIRenderer
from app.interfaces.telegram.workflows.base_workflow import TelegramWorkflowResponse

from .enhanced_workflow import (
    AgeStepHandler,
    GenderStepHandler,
    RestartLocationStepHandler,
    TelegramEnhancedWorkflow,
)

logger = get_logger(__name__)


class TelegramRestartWorkflow(TelegramEnhancedWorkflow):
    """Restart workflow for updating existing user profile information."""

    def __init__(self, state: WorkflowState):
        super().__init__(state)
        logger.info("Initialized TelegramRestartWorkflow")

    def _initialize_handlers(self):
        """Initialize step handlers with restart-specific handlers."""
        self.step_handlers[WorkflowStep.GENDER.value] = GenderStepHandler(self)
        self.step_handlers[WorkflowStep.AGE.value] = AgeStepHandler(self)
        self.step_handlers[WorkflowStep.LOCATION.value] = RestartLocationStepHandler(
            self
        )

    async def start(self) -> TelegramWorkflowResponse:
        """Start the restart workflow with a different message."""
        self.update_step(WorkflowStep.GENDER)
        return TelegramWorkflowResponse(
            text=MessageFormatter.restart_welcome_message(),
            reply_markup=UIRenderer.gender_selection_keyboard(),
        )

    async def process_message(
        self, message: TelegramMessage
    ) -> Optional[TelegramWorkflowResponse]:
        """Process message with enhanced infrastructure."""
        logger.info(
            f"Processing restart message in step {self.state.current_step}: {message.text}"
        )
        return await super().process_message(message)

    async def process_callback_query(
        self, callback_data: str, user: TelegramUser
    ) -> Optional[TelegramWorkflowResponse]:
        """Process callback query with enhanced infrastructure."""
        logger.info(
            f"Processing restart callback in step {self.state.current_step}: {callback_data}"
        )
        return await super().process_callback_query(callback_data, user)
