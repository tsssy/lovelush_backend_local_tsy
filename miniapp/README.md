# LoveLush Mini App

A simple Telegram Mini App frontend for the LoveLush bot.

## Features

- 🔑 Token handling from URL parameters and localStorage
- 👤 User profile display via backend API calls
- 🔄 Token refresh functionality
- 🎨 Telegram-themed UI with proper styling
- 📱 Responsive design for mobile devices
- 🐛 Debug information display
- 🔗 Backend API integration

## Quick Start

1. **Start the mini app server:**

   ```bash
   cd miniapp
   python3 serve.py
   ```

   Or using npm:

   ```bash
   npm run start
   ```

2. **Update backend configuration:**
   Make sure your backend has the correct miniapp URL in settings:

   ```bash
   export MINIAPP_URL="http://localhost:8080"
   # or use ngrok for external access:
   # export MINIAPP_URL="https://your-ngrok-id.ngrok.io"
   ```

3. **Update frontend configuration:**
   Edit `index.html` and update the `BACKEND_URL` in the CONFIG object:

   ```javascript
   const CONFIG = {
       BACKEND_URL: 'https://your-backend-ngrok-url.com', // Update this
       API_BASE: '/api/v1'
   };
   ```

## How it works

1. **User flow:**
   - User sends `/start` command to Telegram bot
   - Bot completes onboarding workflow (gender → age → location)
   - Bot generates JWT token and creates mini app URL: `http://localhost:8080?token=<jwt>`
   - User clicks the mini app link
   - Mini app loads, extracts token from URL, and stores it
   - Mini app calls backend API to fetch user profile
   - User sees their profile information

2. **Token management:**
   - Tokens are extracted from URL parameters
   - Tokens are stored in localStorage for persistence
   - Refresh tokens are supported (if available)
   - Failed API calls trigger automatic token refresh

3. **Telegram WebApp integration:**
   - Uses Telegram WebApp SDK for proper theming
   - Displays debug information about WebApp context
   - Supports Telegram's color scheme and theme parameters

## Development

### Testing with ngrok

1. **Start the mini app server:**

   ```bash
   python3 serve.py
   ```

2. **Expose with ngrok:**

   ```bash
   ngrok http 8080
   ```

3. **Update your backend's miniapp_url setting:**

   ```bash
   export MINIAPP_URL="https://your-ngrok-id.ngrok.io"
   ```

4. **Test with your Telegram bot**

### File Structure

```
miniapp/
├── index.html          # Main mini app file
├── serve.py           # Python HTTP server
├── package.json       # Package configuration
└── README.md          # This file
```

## Configuration

### Backend Configuration

Update `app/core/config/settings.py`:

```python
miniapp_url: str = "http://localhost:8080"  # or your ngrok URL
```

### Frontend Configuration

Update the CONFIG object in `index.html`:

```javascript
const CONFIG = {
    BACKEND_URL: 'https://your-backend-ngrok-url.com',
    API_BASE: '/api/v1'
};
```

## API Endpoints Used

- `GET /api/v1/users/me` - Get current user profile
- `POST /api/v1/auth/refresh` - Refresh access token

## Telegram Mini App Integration

The app integrates with Telegram's Mini App platform:

- Uses `telegram-web-app.js` SDK
- Supports Telegram theming and color schemes
- Handles initData for authentication context
- Responsive design for Telegram's webview

## Troubleshooting

1. **Token not found:**
   - Make sure the bot is generating the correct mini app URL
   - Check browser console for errors
   - Verify the token parameter in the URL

2. **Backend API calls fail:**
   - Update BACKEND_URL in the frontend configuration
   - Make sure backend is running and accessible
   - Check CORS settings in backend

3. **Telegram WebApp not working:**
   - Make sure you're accessing via Telegram's Mini App context
   - Check if telegram-web-app.js is loading properly
   - Review debug information displayed in the app
