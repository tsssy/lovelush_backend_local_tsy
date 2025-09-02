"""Base workflow classes and interfaces."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel

from app.interfaces.telegram.common.types import (
    TelegramMessage,
    TelegramReplyMarkup,
    TelegramUser,
)
from app.interfaces.telegram.models.workflow import WorkflowState, WorkflowStep


class TelegramWorkflowResponse(BaseModel):
    """Workflow response model using SDK ReplyMarkup types."""

    text: str
    reply_markup: Optional[TelegramReplyMarkup] = None
    parse_mode: str = "HTML"

    class Config:
        arbitrary_types_allowed = True


class TelegramBaseWorkflow(ABC):
    """Base class for all workflows."""

    def __init__(self, state: WorkflowState):
        self.state = state

    @abstractmethod
    async def start(self) -> TelegramWorkflowResponse:
        """Start the workflow."""
        pass

    @abstractmethod
    async def process_message(
        self, message: TelegramMessage
    ) -> Optional[TelegramWorkflowResponse]:
        """Process user message."""
        pass

    @abstractmethod
    async def process_callback_query(
        self, callback_data: str, user: TelegramUser
    ) -> Optional[TelegramWorkflowResponse]:
        """Process callback query."""
        pass

    @abstractmethod
    async def cancel(self) -> TelegramWorkflowResponse:
        """Cancel the workflow."""
        pass

    def is_expired(self) -> bool:
        """Check if workflow has expired."""
        return datetime.now() > self.state.expires_at

    def update_step(self, step: WorkflowStep, data: Optional[Dict[str, Any]] = None):
        """Update workflow step and data."""
        self.state.current_step = step
        if data:
            self.state.data.update(data)
