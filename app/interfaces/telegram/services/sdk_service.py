"""Telegram service using official python-telegram-bot SDK."""

from typing import Dict, List, Optional

from telegram.error import TelegramError

from app.core.config.settings import settings
from app.core.logging import get_logger
from app.interfaces.telegram.common.responses import (
    BotInfo,
    BotInfoResponse,
    MessageResponse,
    MessageResult,
    TelegramResponse,
    WebhookResponse,
)
from app.interfaces.telegram.common.types import (
    TelegramBot,
    TelegramBotCommand,
    TelegramLabeledPrice,
    TelegramReplyMarkup,
)

logger = get_logger(__name__)


class TelegramSDKService:
    """Service for Telegram operations using official SDK."""

    def __init__(self):
        """Initialize the Telegram bot service."""
        if not settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

        self._bot = TelegramBot(
            token=settings.telegram_bot_token, local_mode=settings.debug
        )

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[TelegramReplyMarkup] = None,
        disable_web_page_preview: bool = True,
    ) -> MessageResponse:
        """Send a message to a chat."""
        try:
            message = await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview,
            )

            result = MessageResult.from_message(message)
            return TelegramResponse.success_response(result)

        except TelegramError as e:
            logger.error(f"Failed to send message: {e}")
            return TelegramResponse.error_response(e)

    async def get_me(self) -> BotInfoResponse:
        """Get bot information."""
        try:
            bot_user = await self._bot.get_me()
            bot_info = BotInfo.from_user(bot_user)
            return TelegramResponse.success_response(bot_info)

        except TelegramError as e:
            logger.error(f"Failed to get bot info: {e}")
            return TelegramResponse.error_response(e)

    async def set_webhook(
        self, url: Optional[str] = None, secret_token: Optional[str] = None
    ) -> WebhookResponse:
        """Set webhook for the bot."""
        webhook_url = url or settings.telegram_webhook_url
        webhook_secret = secret_token or settings.telegram_webhook_secret

        try:
            await self._bot.set_webhook(url=webhook_url, secret_token=webhook_secret)
            return TelegramResponse.success_response(True)

        except TelegramError as e:
            logger.error(f"Failed to set webhook: {e}")
            return TelegramResponse.error_response(e)

    async def delete_webhook(self) -> WebhookResponse:
        """Delete webhook."""
        try:
            await self._bot.delete_webhook()
            return TelegramResponse.success_response(True)

        except TelegramError as e:
            logger.error(f"Failed to delete webhook: {e}")
            return TelegramResponse.error_response(e)

    async def set_my_commands(self, commands: List[Dict[str, str]]) -> WebhookResponse:
        """Set bot commands."""
        try:
            bot_commands = [
                TelegramBotCommand(
                    command=cmd["command"], description=cmd["description"]
                )
                for cmd in commands
            ]

            await self._bot.set_my_commands(bot_commands)
            return TelegramResponse.success_response(True)

        except TelegramError as e:
            logger.error(f"Failed to set commands: {e}")
            return TelegramResponse.error_response(e)

    async def answer_pre_checkout_query(
        self, pre_checkout_query_id: str, ok: bool, error_message: Optional[str] = None
    ) -> TelegramResponse:
        """Answer pre-checkout query."""
        try:
            await self._bot.answer_pre_checkout_query(
                pre_checkout_query_id=pre_checkout_query_id,
                ok=ok,
                error_message=error_message,
            )
            return TelegramResponse.success_response(True)

        except TelegramError as e:
            logger.error(f"Failed to answer pre-checkout query: {e}")
            return TelegramResponse.error_response(e)

    async def create_invoice_link(
        self,
        title: str,
        description: str,
        payload: str,
        currency: str,
        prices: List[TelegramLabeledPrice],
        provider_token: Optional[str] = None,  # Made optional for XTR payments
        max_tip_amount: Optional[int] = None,
        suggested_tip_amounts: Optional[List[int]] = None,
        provider_data: Optional[str] = None,
        photo_url: Optional[str] = None,
        photo_size: Optional[int] = None,
        photo_width: Optional[int] = None,
        photo_height: Optional[int] = None,
        need_name: Optional[bool] = None,
        need_phone_number: Optional[bool] = None,
        need_email: Optional[bool] = None,
        need_shipping_address: Optional[bool] = None,
        send_phone_number_to_provider: Optional[bool] = None,
        send_email_to_provider: Optional[bool] = None,
        is_flexible: Optional[bool] = None,
    ) -> TelegramResponse:
        """Create invoice link for payment."""
        try:
            # Build parameters dict, conditionally including provider_token
            params = {
                "title": title,
                "description": description,
                "payload": payload,
                "currency": currency,
                "prices": prices,
                "max_tip_amount": max_tip_amount,
                "suggested_tip_amounts": suggested_tip_amounts,
                "provider_data": provider_data,
                "photo_url": photo_url,
                "photo_size": photo_size,
                "photo_width": photo_width,
                "photo_height": photo_height,
                "need_name": need_name,
                "need_phone_number": need_phone_number,
                "need_email": need_email,
                "need_shipping_address": need_shipping_address,
                "send_phone_number_to_provider": send_phone_number_to_provider,
                "send_email_to_provider": send_email_to_provider,
                "is_flexible": is_flexible,
            }

            # Only include provider_token if it's provided (for non-XTR currencies)
            if provider_token is not None:
                params["provider_token"] = provider_token

            # Remove None values to clean up the API call
            params = {k: v for k, v in params.items() if v is not None}

            invoice_link = await self._bot.create_invoice_link(**params)

            return TelegramResponse.success_response({"invoice_url": invoice_link})

        except TelegramError as e:
            logger.error(f"Failed to create invoice link: {e}")
            return TelegramResponse.error_response(e)

    async def close(self):
        """Close the bot session."""
        try:
            await self._bot.shutdown()
        except Exception as e:
            logger.error(f"Error closing bot session: {e}")


# Global instance
telegram_sdk_service = TelegramSDKService()
