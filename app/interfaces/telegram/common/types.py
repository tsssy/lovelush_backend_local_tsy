"""Centralized type aliases for Telegram SDK classes."""

from typing import Union

from telegram import Bot as TelegramBot
from telegram import BotCommand as TelegramBotCommand
from telegram import CallbackQuery as TelegramCallbackQuery
from telegram import ForceReply as TelegramForceReply
from telegram import InlineKeyboardButton as TelegramInlineKeyboardButton
from telegram import InlineKeyboardMarkup as TelegramInlineKeyboardMarkup
from telegram import InlineQuery as TelegramInlineQuery
from telegram import LabeledPrice as TelegramLabeledPrice
from telegram import Message as TelegramMessage
from telegram import ReplyKeyboardMarkup as TelegramReplyKeyboardMarkup
from telegram import ReplyKeyboardRemove as TelegramReplyKeyboardRemove
from telegram import Update as TelegramUpdate
from telegram import User as TelegramUser
from telegram import WebAppInfo as TelegramWebAppInfo

TelegramReplyMarkup = Union[
    TelegramForceReply,
    TelegramInlineKeyboardMarkup,
    TelegramReplyKeyboardMarkup,
    TelegramReplyKeyboardRemove,
    None,
]

# Re-export all aliases for easy importing
__all__ = [
    "TelegramBot",
    "TelegramBotCommand",
    "TelegramCallbackQuery",
    "TelegramForceReply",
    "TelegramInlineKeyboardButton",
    "TelegramInlineKeyboardMarkup",
    "TelegramInlineQuery",
    "TelegramLabeledPrice",
    "TelegramMessage",
    "TelegramReplyKeyboardMarkup",
    "TelegramReplyKeyboardRemove",
    "TelegramReplyMarkup",
    "TelegramUpdate",
    "TelegramUser",
    "TelegramWebAppInfo",
]
