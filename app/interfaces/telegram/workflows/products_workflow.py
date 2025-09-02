"""Products workflow for displaying and purchasing products via telegram bot."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.core.dependencies import (
    get_credits_service,
    get_payment_service,
    get_product_service,
    get_user_service,
)
from app.core.logging import get_logger
from app.domain.models.payment import PaymentCreate
from app.interfaces.telegram.common.types import (
    TelegramInlineKeyboardButton,
    TelegramInlineKeyboardMarkup,
    TelegramMessage,
    TelegramUser,
)
from app.interfaces.telegram.models.workflow import WorkflowState, WorkflowStep
from app.interfaces.telegram.templates.product_messages import (
    button_template,
    payment_template,
    product_detail_template,
    product_list_template,
)
from app.interfaces.telegram.workflows.base_workflow import TelegramWorkflowResponse
from app.interfaces.telegram.workflows.enhanced_workflow import (
    NavigationMixin,
    StepAction,
    StepHandler,
    StepResult,
    TelegramEnhancedWorkflow,
)

logger = get_logger(__name__)


class ProductsListStepHandler(StepHandler, NavigationMixin):
    """Handler for products list display step."""

    def __init__(self, workflow: "TelegramProductsWorkflow"):
        super().__init__(workflow)
        # Get services from dependency injection container
        self.product_service = get_product_service()

    async def enter_step(self) -> TelegramWorkflowResponse:
        """Enter products list step."""
        # Get pagination parameters from workflow data
        page = self.workflow.state.data.get("page", 0)
        page_size = 5  # Show 5 products per page

        try:
            # Get one extra product to check if there are more pages
            products = await self.product_service.get_products_sorted_by_sequence(
                limit=page_size + 1, offset=page * page_size
            )

            if not products:
                if page == 0:
                    return TelegramWorkflowResponse(
                        text=product_list_template.no_products,
                    )
                else:
                    # No more products, go back to previous page
                    return await self._show_products_page(page - 1, page_size)

            # Check if there are more pages
            has_next_page = len(products) > page_size
            if has_next_page:
                products = products[:page_size]  # Remove the extra product

            return await self._show_products_page(
                page, page_size, products, has_next_page
            )

        except Exception as e:
            logger.error(f"Error loading products: {e}", exc_info=True)
            return TelegramWorkflowResponse(
                text="❌ Sorry, there was an error loading products. Please try again later.",
            )

    async def _show_products_page(
        self,
        page: int,
        page_size: int,
        products=None,
        has_next_page: Optional[bool] = None,
    ) -> TelegramWorkflowResponse:
        """Show products page with pagination."""
        if products is None:
            # Fetch products for this page using injected service
            products = await self.product_service.get_products_sorted_by_sequence(
                limit=page_size + 1, offset=page * page_size
            )
            if not products:
                return TelegramWorkflowResponse(
                    text=product_list_template.no_products,
                )

            has_next_page = len(products) > page_size
            if has_next_page:
                products = products[:page_size]

        # Create product list message and keyboard using templates
        message_parts = [
            product_list_template.format_header(page, has_next_page or False)
        ]
        keyboard_buttons = []

        for i, product in enumerate(products, 1):
            # Show global product number (across all pages)
            product_number = page * page_size + i

            # Format product item using template
            product_item = product_list_template.format_product_item(
                product_number, product
            )
            message_parts.append(product_item)

            # Add description if available
            description = product_list_template.format_description(product)
            if description:
                message_parts.append(description)
            message_parts.append("")

            # Add button for this product using template
            button_text = button_template.format_product_button(product_number, product)
            keyboard_buttons.append(
                [
                    TelegramInlineKeyboardButton(
                        text=button_text,
                        callback_data=f"product:{product.id}",
                    )
                ]
            )

        message_parts.append(product_list_template.footer)

        # Add pagination buttons if needed using templates
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(
                TelegramInlineKeyboardButton(
                    text=button_template.previous_button,
                    callback_data=f"page:{page - 1}",
                )
            )
        if has_next_page:
            pagination_buttons.append(
                TelegramInlineKeyboardButton(
                    text=button_template.next_button, callback_data=f"page:{page + 1}"
                )
            )

        if pagination_buttons:
            keyboard_buttons.append(pagination_buttons)

        keyboard = TelegramInlineKeyboardMarkup(keyboard_buttons)

        final_message = "\n".join(message_parts)

        return TelegramWorkflowResponse(
            text=final_message,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    async def handle_message(
        self, text: str, message_data: Dict[str, Any]  # type: ignore[unused]
    ) -> StepResult:
        """Handle text input - not expected for products list step."""
        return StepResult(
            action=StepAction.STAY,
            response=TelegramWorkflowResponse(
                text="Please select a product from the list above by tapping on it."
            ),
        )

    async def handle_callback(self, callback_data: str) -> StepResult:
        """Handle callback for product selection and pagination."""
        if callback_data.startswith("product:"):
            product_id = callback_data.split(":")[1]

            return self.create_next_result(
                WorkflowStep.PRODUCT_DETAIL,
                {"selected_product_id": product_id},
                "Loading product details...",
            )
        elif callback_data.startswith("page:"):
            # Handle pagination
            page = int(callback_data.split(":")[1])

            return StepResult(
                action=StepAction.STAY,
                response=await self._show_products_page(page, 5),
                data={"page": page},
            )

        return StepResult(
            action=StepAction.STAY,
            response=TelegramWorkflowResponse(
                text="Please select a product from the list above by tapping on it."
            ),
        )

    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate product selection."""
        return "selected_product_id" in input_data and input_data["selected_product_id"]


class ProductDetailStepHandler(StepHandler, NavigationMixin):
    """Handler for product detail display and purchase step."""

    def __init__(self, workflow: "TelegramProductsWorkflow"):
        super().__init__(workflow)
        # Get services from dependency injection container
        self.product_service = get_product_service()

    async def enter_step(self) -> TelegramWorkflowResponse:
        """Enter product detail step."""
        product_id = self.workflow.state.data.get("selected_product_id")
        if not product_id:
            return TelegramWorkflowResponse(
                text=product_detail_template.not_found,
            )

        try:
            product = await self.product_service.get_product(product_id)
            if not product:
                return TelegramWorkflowResponse(
                    text=product_detail_template.not_found,
                )

            if not product.is_available:
                return TelegramWorkflowResponse(
                    text=product_detail_template.not_available,
                )

            # Format product details using template
            message = product_detail_template.format_product_detail(product)

            # Create purchase buttons using templates
            keyboard_buttons = [
                [
                    TelegramInlineKeyboardButton(
                        text=button_template.format_buy_button(product),
                        callback_data=f"purchase:{product.id}",
                    )
                ],
                [
                    TelegramInlineKeyboardButton(
                        text=button_template.back_to_list, callback_data="back_to_list"
                    )
                ],
            ]

            keyboard = TelegramInlineKeyboardMarkup(keyboard_buttons)

            return TelegramWorkflowResponse(
                text=message, reply_markup=keyboard, parse_mode="HTML"
            )

        except Exception as e:
            logger.error(f"Error loading product details: {e}")
            return TelegramWorkflowResponse(
                text=product_detail_template.not_available,
            )

    async def handle_message(
        self, text: str, message_data: Dict[str, Any]  # type: ignore[unused]
    ) -> StepResult:
        """Handle text input - not expected for product detail step."""
        return StepResult(
            action=StepAction.STAY,
            response=TelegramWorkflowResponse(
                text="Please use the buttons below to purchase the product or go back."
            ),
        )

    async def handle_callback(self, callback_data: str) -> StepResult:
        """Handle callback for purchase or navigation."""
        # Handle product selection callbacks (in case user clicks product list button while in detail view)
        if callback_data.startswith("product:"):
            product_id = callback_data.split(":")[1]

            return self.create_next_result(
                WorkflowStep.PRODUCT_DETAIL,
                {"selected_product_id": product_id},
                "Loading product details...",
            )
        elif callback_data.startswith("purchase:"):
            product_id = callback_data.split(":")[1]

            return self.create_next_result(
                WorkflowStep.PAYMENT_CONFIRMATION,
                {"purchase_product_id": product_id},
                "Preparing payment...",
            )
        elif callback_data == "back_to_list":
            return self.create_next_result(
                WorkflowStep.PRODUCTS_LIST,
                {},
                "Returning to products list...",
            )

        return StepResult(
            action=StepAction.STAY,
            response=TelegramWorkflowResponse(
                text="Please use the buttons below to purchase or go back."
            ),
        )

    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate purchase input."""
        return "purchase_product_id" in input_data and input_data["purchase_product_id"]


class PaymentConfirmationStepHandler(StepHandler, NavigationMixin):
    """Handler for payment confirmation and processing step."""

    def __init__(self, workflow: "TelegramProductsWorkflow"):
        super().__init__(workflow)
        # Get services from dependency injection container
        self.user_service = get_user_service()
        self.product_service = get_product_service()
        self.credits_service = get_credits_service()
        self.payment_service = get_payment_service()

    async def enter_step(self) -> TelegramWorkflowResponse:
        """Enter payment confirmation step."""
        product_id = self.workflow.state.data.get("purchase_product_id")
        if not product_id:
            return TelegramWorkflowResponse(
                text=payment_template.payment_error,
            )

        try:
            # Get user
            user = await self.user_service.get_user_by_telegram_id(
                str(self.workflow.state.telegram_user_id)
            )
            if not user:
                return TelegramWorkflowResponse(
                    text=payment_template.user_not_found,
                )

            # Get product
            product = await self.product_service.get_product(product_id)
            if not product or not product.is_available:
                return TelegramWorkflowResponse(
                    text=payment_template.product_unavailable,
                )

            # Get user's current credits
            user_credits = await self.credits_service.get_user_credits(str(user.id))
            current_balance = user_credits.current_balance if user_credits else 0

            # Create payment record using injected service
            payment_create = PaymentCreate(
                telegram_user_id=str(self.workflow.state.telegram_user_id),
                product_id=product_id,
                amount=product.price,
                currency=product.currency,
                invoice_payload=f"product_{product_id}_{user.id}",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )

            payment = await self.payment_service.create_payment(payment_create)

            # Create invoice URL using injected service
            invoice_url = await self.payment_service.create_telegram_invoice_url(
                payment, product
            )

            new_balance_after = current_balance + product.credits

            # Format message using template
            message = payment_template.format_payment_confirmation(
                product, current_balance, new_balance_after
            )

            keyboard_buttons = []
            if invoice_url:
                keyboard_buttons.append(
                    [
                        TelegramInlineKeyboardButton(
                            text=button_template.format_pay_button(product),
                            url=invoice_url,
                        )
                    ]
                )

            keyboard_buttons.extend(
                [
                    [
                        TelegramInlineKeyboardButton(
                            text=button_template.back_to_product,
                            callback_data="back_to_product",
                        )
                    ],
                    [
                        TelegramInlineKeyboardButton(
                            text=button_template.cancel_button,
                            callback_data="cancel_purchase",
                        )
                    ],
                ]
            )

            keyboard = TelegramInlineKeyboardMarkup(keyboard_buttons)

            # Store payment ID for tracking
            return StepResult(
                action=StepAction.STAY,
                response=TelegramWorkflowResponse(
                    text=message, reply_markup=keyboard, parse_mode="HTML"
                ),
                data={"payment_id": str(payment.id)},
            ).response

        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            return TelegramWorkflowResponse(
                text=payment_template.processing_error,
            )

    async def handle_message(
        self, text: str, message_data: Dict[str, Any]  # type: ignore[unused]
    ) -> StepResult:
        """Handle text input - not expected for payment step."""
        return StepResult(
            action=StepAction.STAY,
            response=TelegramWorkflowResponse(
                text="Please use the payment link or buttons below to complete your purchase."
            ),
        )

    async def handle_callback(self, callback_data: str) -> StepResult:
        """Handle callback for payment navigation."""
        if callback_data == "back_to_product":
            return self.create_next_result(
                WorkflowStep.PRODUCT_DETAIL,
                {},
                "Returning to product details...",
            )
        elif callback_data == "cancel_purchase":
            return StepResult(
                action=StepAction.COMPLETE,
                response=TelegramWorkflowResponse(
                    text="❌ Purchase cancelled. Use /products to browse products again."
                ),
            )

        return StepResult(
            action=StepAction.STAY,
            response=TelegramWorkflowResponse(
                text="Please complete your payment or use the buttons below."
            ),
        )

    async def validate_input(self, input_data: Dict[str, Any]) -> bool:  # type: ignore[unused]
        """Validate payment input."""
        return True  # No specific validation needed for payment step


class TelegramProductsWorkflow(TelegramEnhancedWorkflow):
    """Products workflow with step-based architecture for showing and purchasing products."""

    def __init__(self, state: WorkflowState):
        super().__init__(state)

    def _initialize_handlers(self):
        """Initialize step handlers for products workflow with dependency injection."""
        # Initialize parent handlers first (though we won't use them)
        super()._initialize_handlers()

        # Override with our product-specific handlers that use dependency injection
        self.step_handlers[WorkflowStep.PRODUCTS_LIST.value] = ProductsListStepHandler(
            self
        )
        self.step_handlers[WorkflowStep.PRODUCT_DETAIL.value] = (
            ProductDetailStepHandler(self)
        )
        self.step_handlers[WorkflowStep.PAYMENT_CONFIRMATION.value] = (
            PaymentConfirmationStepHandler(self)
        )

    async def start(self) -> TelegramWorkflowResponse:
        """Start the products workflow."""
        self.update_step(WorkflowStep.PRODUCTS_LIST)
        handler = self.step_handlers[WorkflowStep.PRODUCTS_LIST.value]
        response = await handler.enter_step()
        return response

    async def process_message(
        self, message: TelegramMessage
    ) -> Optional[TelegramWorkflowResponse]:
        """Process message with products workflow handling."""
        return await super().process_message(message)

    async def process_callback_query(
        self, callback_data: str, user: TelegramUser
    ) -> Optional[TelegramWorkflowResponse]:
        """Process callback query with products workflow handling."""
        return await super().process_callback_query(callback_data, user)
