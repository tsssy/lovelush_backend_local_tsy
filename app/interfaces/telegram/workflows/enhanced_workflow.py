"""Enhanced workflow execution infrastructure."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.domain.models.user import Gender, OnboardingStatus, UserUpdate
from app.domain.services.user_service import UserService
from app.infrastructure.database.repositories.workflow_repository import (
    WorkflowRepository,
)

from ..common.utils import get_miniapp_url
from ..skill.rendering import LOCATION_MAP, MessageFormatter, UIRenderer
from .base_workflow import TelegramBaseWorkflow, TelegramWorkflowResponse, WorkflowStep

logger = get_logger(__name__)


class StepAction(Enum):
    """Available step actions."""

    NEXT = "next"
    BACK = "back"
    CANCEL = "cancel"
    COMPLETE = "complete"
    STAY = "stay"


class StepResult:
    """Result of step execution."""

    def __init__(
        self,
        action: StepAction,
        response: TelegramWorkflowResponse,
        next_step: Optional[WorkflowStep] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        self.action = action
        self.response = response
        self.next_step = next_step
        self.data = data or {}


class StepHandler(ABC):
    """Abstract base class for step handlers."""

    def __init__(self, workflow: "TelegramEnhancedWorkflow"):
        self.workflow = workflow

    @abstractmethod
    async def enter_step(self) -> TelegramWorkflowResponse:
        """Called when entering this step."""
        pass

    @abstractmethod
    async def handle_message(
        self, text: str, message_data: Dict[str, Any]
    ) -> StepResult:
        """Handle text message input."""
        pass

    @abstractmethod
    async def handle_callback(self, callback_data: str) -> StepResult:
        """Handle callback query."""
        pass

    @abstractmethod
    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input data."""
        pass


class NavigationMixin:
    """Mixin for common navigation patterns."""

    def create_back_result(self, previous_step: WorkflowStep) -> StepResult:
        """Create result for back navigation."""
        return StepResult(
            action=StepAction.BACK,
            response=TelegramWorkflowResponse(text="Going back..."),
            next_step=previous_step,
        )

    def create_cancel_result(self) -> StepResult:
        """Create result for cancellation."""
        return StepResult(
            action=StepAction.CANCEL,
            response=TelegramWorkflowResponse(
                text=MessageFormatter.cancellation_message(),
            ),
        )

    def create_next_result(
        self, next_step: WorkflowStep, data: Dict[str, Any], message: str
    ) -> StepResult:
        """Create result for next step."""
        return StepResult(
            action=StepAction.NEXT,
            response=TelegramWorkflowResponse(text=message),
            next_step=next_step,
            data=data,
        )


class GenderStepHandler(StepHandler, NavigationMixin):
    """Handler for gender selection step."""

    async def enter_step(self) -> TelegramWorkflowResponse:
        """Enter gender selection step."""
        return TelegramWorkflowResponse(
            text=MessageFormatter.welcome_message(),
            reply_markup=UIRenderer.gender_selection_keyboard(),
        )

    async def handle_message(
        self, text: str, message_data: Dict[str, Any]
    ) -> StepResult:
        """Handle text input - not expected for gender step."""
        return StepResult(
            action=StepAction.STAY,
            response=TelegramWorkflowResponse(
                text=MessageFormatter.invalid_input_message()
            ),
        )

    async def handle_callback(self, callback_data: str) -> StepResult:
        """Handle callback for gender selection."""
        if callback_data.startswith("gender:"):
            gender = callback_data.split(":")[1]
            logger.info(f"User {self.workflow.state.user_id} selected gender: {gender}")
            return self.create_next_result(
                WorkflowStep.AGE,
                {"gender": gender},
                MessageFormatter.gender_confirmed_message(gender),
            )

        return StepResult(
            action=StepAction.STAY,
            response=TelegramWorkflowResponse(
                text=MessageFormatter.invalid_input_message()
            ),
        )

    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate gender input."""
        gender = input_data.get("gender")
        return gender in ["male", "female"]


class AgeStepHandler(StepHandler, NavigationMixin):
    """Handler for age selection step."""

    async def enter_step(self) -> TelegramWorkflowResponse:
        """Enter age selection step."""
        return TelegramWorkflowResponse(
            text="Please enter your age (must be between 18 and 100):",
        )

    async def handle_message(
        self, text: str, message_data: Dict[str, Any]
    ) -> StepResult:
        """Handle text input for age."""
        try:
            age = int(text.strip())
            if 18 <= age <= 100:
                logger.info(
                    f"User {self.workflow.state.user_id} entered valid age: {age}"
                )
                return self.create_next_result(
                    WorkflowStep.LOCATION,
                    {"age": age},
                    MessageFormatter.age_confirmed_message(age),
                )
            else:
                return StepResult(
                    action=StepAction.STAY,
                    response=TelegramWorkflowResponse(
                        text=MessageFormatter.age_validation_error()
                    ),
                )
        except ValueError:
            return StepResult(
                action=StepAction.STAY,
                response=TelegramWorkflowResponse(
                    text=MessageFormatter.age_format_error()
                ),
            )

    async def handle_callback(self, callback_data: str) -> StepResult:
        """Handle callback for age selection - no callbacks expected for manual input."""
        return StepResult(
            action=StepAction.STAY,
            response=TelegramWorkflowResponse(
                text="Please enter your age as a number."
            ),
        )

    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate age input."""
        age = input_data.get("age")
        if age is not None:
            return 18 <= age <= 100
        return False


class LocationStepHandler(StepHandler, NavigationMixin):
    """Handler for location selection step."""

    async def enter_step(self) -> TelegramWorkflowResponse:
        """Enter location selection step."""
        return TelegramWorkflowResponse(
            text="Please select your country/region:",
            reply_markup=UIRenderer.location_selection_keyboard(),
        )

    async def handle_message(
        self, text: str, message_data: Dict[str, Any]
    ) -> StepResult:
        """Handle text input for location - only callbacks expected."""
        return StepResult(
            action=StepAction.STAY,
            response=TelegramWorkflowResponse(
                text="Please select a country from the buttons above."
            ),
        )

    async def handle_callback(self, callback_data: str) -> StepResult:
        """Handle callback for location selection."""
        if callback_data.startswith("location:"):
            location_key = callback_data.split(":")[1]

            location = LOCATION_MAP.get(
                location_key, location_key.replace("_", " ").title()
            )
            logger.info(
                f"User {self.workflow.state.user_id} selected location: {location}"
            )

            # Update user with completed onboarding status
            data = {"location": location}
            final_data = {**self.workflow.state.data, **data}

            # Handle user onboarding completion
            try:
                user_service = UserService()
                telegram_user_id = str(self.workflow.state.telegram_user_id)
                existing_user = await user_service.get_user_by_telegram_id(
                    telegram_user_id
                )

                if existing_user:
                    # Create UserUpdate with only the fields we want to update
                    update_data = {
                        "age": final_data.get("age"),
                        "location": final_data.get("location"),
                        "onboarding_status": OnboardingStatus.COMPLETED,
                    }
                    if final_data.get("gender"):
                        update_data["gender"] = Gender(final_data["gender"])

                    user_update = UserUpdate(**update_data)

                    await user_service.update_user(existing_user.id, user_update)
                    logger.info(
                        f"Updated user {existing_user.id} with completed onboarding"
                    )
                else:
                    logger.warning(
                        f"No user found for telegram_user_id {telegram_user_id} during workflow completion"
                    )

            except Exception as e:
                logger.error(f"Failed to update user onboarding status: {e}")

            completion_result = MessageFormatter.completion_message(
                final_data, get_miniapp_url()
            )
            return StepResult(
                action=StepAction.COMPLETE,
                response=TelegramWorkflowResponse(
                    text=completion_result["text"],
                    reply_markup=completion_result.get("reply_markup"),
                ),
                data=data,
            )

        return StepResult(
            action=StepAction.STAY,
            response=TelegramWorkflowResponse(
                text="Please select a country from the buttons above."
            ),
        )

    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate location input."""
        location = input_data.get("location")
        return location is not None and len(str(location).strip()) >= 2


class RestartLocationStepHandler(StepHandler, NavigationMixin):
    """Handler for location selection step in restart workflow - updates existing user."""

    async def enter_step(self) -> TelegramWorkflowResponse:
        """Enter location selection step."""
        return TelegramWorkflowResponse(
            text="Please select your updated country/region:",
            reply_markup=UIRenderer.location_selection_keyboard(),
        )

    async def handle_message(
        self, text: str, message_data: Dict[str, Any]
    ) -> StepResult:
        """Handle text input for location - only callbacks expected."""
        return StepResult(
            action=StepAction.STAY,
            response=TelegramWorkflowResponse(
                text="Please select a country from the buttons above."
            ),
        )

    async def handle_callback(self, callback_data: str) -> StepResult:
        """Handle callback for location selection - updates existing user."""
        if callback_data.startswith("location:"):
            location_key = callback_data.split(":")[1]
            location = LOCATION_MAP.get(
                location_key, location_key.replace("_", " ").title()
            )

            # Prepare data for user update
            data = {"location": location}
            final_data = {**self.workflow.state.data, **data}

            # Update existing user instead of creating new one
            user_service = UserService()
            try:
                telegram_user_id = str(self.workflow.state.telegram_user_id)
                existing_user = await user_service.get_user_by_telegram_id(
                    telegram_user_id
                )

                if existing_user:
                    # Create UserUpdate with only the fields we want to update
                    update_data = {
                        "age": final_data.get("age"),
                        "location": final_data.get("location"),
                    }
                    if final_data.get("gender"):
                        update_data["gender"] = Gender(final_data["gender"])

                    user_update = UserUpdate(**update_data)
                    await user_service.update_user(existing_user.id, user_update)

                    # Use clean Mini App URL - authentication via Telegram initData
                    miniapp_url = get_miniapp_url()

                    completion_result = MessageFormatter.restart_completion_message(
                        final_data, miniapp_url
                    )
                    return StepResult(
                        action=StepAction.COMPLETE,
                        response=TelegramWorkflowResponse(
                            text=completion_result["text"],
                            reply_markup=completion_result.get("reply_markup"),
                        ),
                        data=data,
                    )
                else:
                    # User not found, fallback message
                    return StepResult(
                        action=StepAction.COMPLETE,
                        response=TelegramWorkflowResponse(
                            text="❌ Profile not found. Please use /start to create your profile.",
                        ),
                        data=data,
                    )

            except Exception as e:
                logger.error(f"Failed to update user: {e}")
                # Fallback without user update
                completion_result = MessageFormatter.restart_completion_message(
                    final_data
                )
                return StepResult(
                    action=StepAction.COMPLETE,
                    response=TelegramWorkflowResponse(
                        text=completion_result["text"],
                        reply_markup=completion_result.get("reply_markup"),
                    ),
                    data=data,
                )

        return StepResult(
            action=StepAction.STAY,
            response=TelegramWorkflowResponse(
                text="Please select a country from the buttons above."
            ),
        )

    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate location input."""
        location = input_data.get("location")
        return location is not None and len(str(location).strip()) >= 2


class TelegramEnhancedWorkflow(TelegramBaseWorkflow):
    """Enhanced workflow with step-based execution and database persistence."""

    def __init__(self, state):
        super().__init__(state)
        self.step_handlers: Dict[str, StepHandler] = {}
        self._repository = WorkflowRepository()
        self._initialize_handlers()

    def _initialize_handlers(self):
        """Initialize step handlers."""
        self.step_handlers[WorkflowStep.GENDER.value] = GenderStepHandler(self)
        self.step_handlers[WorkflowStep.AGE.value] = AgeStepHandler(self)
        self.step_handlers[WorkflowStep.LOCATION.value] = LocationStepHandler(self)

    async def start(self) -> TelegramWorkflowResponse:
        """Start the workflow."""
        logger.info(f"Starting workflow for user {self.state.user_id}")
        self.update_step(WorkflowStep.GENDER)
        handler = self.step_handlers[WorkflowStep.GENDER.value]
        return await handler.enter_step()

    async def process_message(self, message) -> Optional[TelegramWorkflowResponse]:
        """Process message with step-based handling."""
        # current_step should now always be an enum thanks to the field validator
        current_step_key = self.state.current_step.value

        current_handler = self.step_handlers.get(current_step_key)
        if not current_handler:
            logger.error(
                f"User {self.state.user_id} no handler found for step: {current_step_key}"
            )
            return TelegramWorkflowResponse(text="Invalid workflow state.")

        text = message.text.strip() if message.text else ""
        message_data = {
            "location": message.location if hasattr(message, "location") else None
        }

        result = await current_handler.handle_message(text, message_data)
        return await self._process_step_result(result)

    async def process_callback_query(
        self, callback_data: str, user
    ) -> Optional[TelegramWorkflowResponse]:
        """Process callback query with step-based handling."""
        # current_step should now always be an enum thanks to the field validator
        current_step_key = self.state.current_step.value

        current_handler = self.step_handlers.get(current_step_key)
        if not current_handler:
            logger.error(
                f"User {self.state.user_id} no handler found for callback in step: {current_step_key}"
            )
            return TelegramWorkflowResponse(text="Invalid workflow state.")

        result = await current_handler.handle_callback(callback_data)
        return await self._process_step_result(result)

    async def cancel(self) -> TelegramWorkflowResponse:
        """Cancel the workflow."""
        logger.info(f"User {self.state.user_id} cancelled workflow")
        return TelegramWorkflowResponse(
            text=MessageFormatter.cancellation_message(),
        )

    async def _process_step_result(
        self, result: StepResult
    ) -> TelegramWorkflowResponse:
        """Process step result, update state, and persist to database."""
        if result.action == StepAction.NEXT and result.next_step:
            logger.info(
                f"User {self.state.user_id} moving to step: {result.next_step.value}"
            )
            # Update local state
            self.update_step(result.next_step, result.data)

            # Persist to database
            try:
                await self._repository.update_step_and_data(
                    self.state.telegram_user_id,
                    self.state.chat_id,
                    result.next_step,
                    result.data,
                )
            except Exception as e:
                logger.error(
                    f"User {self.state.user_id} failed to persist step data: {e}"
                )

            next_handler = self.step_handlers.get(result.next_step.value)
            if next_handler:
                response = await next_handler.enter_step()
                # Merge with original response if needed
                if result.response.text:
                    response.text = result.response.text + "\n\n" + response.text
                return response

        elif result.action == StepAction.BACK and result.next_step:
            # Update local state
            self.update_step(result.next_step)

            # Persist to database
            try:
                await self._repository.update_step_and_data(
                    self.state.telegram_user_id, self.state.chat_id, result.next_step
                )
            except Exception as e:
                logger.error(
                    f"User {self.state.user_id} failed to persist back step: {e}"
                )

            back_handler = self.step_handlers.get(result.next_step.value)
            if back_handler:
                return await back_handler.enter_step()

        elif result.action == StepAction.COMPLETE:
            logger.info(f"User {self.state.user_id} completed workflow")
            # Update local state
            self.update_step(WorkflowStep.COMPLETE, result.data)

            # Persist to database
            try:
                await self._repository.update_step_and_data(
                    self.state.telegram_user_id,
                    self.state.chat_id,
                    WorkflowStep.COMPLETE,
                    result.data,
                )
            except Exception as e:
                logger.error(
                    f"User {self.state.user_id} failed to persist completion: {e}"
                )

        return result.response
