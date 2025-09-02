# Telegram Bot Integration

This document explains how to configure and use the Telegram bot integration.

## Environment Variables

Add these environment variables to your `.env` file:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/api/v1/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=your_webhook_secret_here
```

## Getting a Bot Token

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Copy the bot token and add it to your environment variables

## Setting Up the Webhook

1. Start your application
2. Make a POST request to `/api/v1/telegram/webhook/set` to register the webhook
3. Verify the webhook is set by calling `/api/v1/telegram/webhook/info`

## Available Endpoints

- `POST /api/v1/telegram/webhook` - Receive webhook updates from Telegram
- `GET /api/v1/telegram/webhook/info` - Get current webhook information
- `POST /api/v1/telegram/webhook/set` - Set webhook URL
- `DELETE /api/v1/telegram/webhook` - Delete webhook
- `GET /api/v1/telegram/me` - Get bot information

## Bot Commands

The bot supports these commands:

- `/start` - Start the bot
- `/help` - Show help message
- `/status` - Check bot status

## Testing

1. Set your environment variables
2. Start the application: `python main.py`
3. Set the webhook using the API endpoint
4. Message your bot on Telegram

## Security

- The webhook endpoint verifies the secret token sent by Telegram
- Configure `TELEGRAM_WEBHOOK_SECRET` for additional security
- Use HTTPS for production webhooks
