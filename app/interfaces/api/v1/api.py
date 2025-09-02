"""API v1 router configuration."""

from fastapi import APIRouter

from app.interfaces.telegram.webhook import router as telegram_router

from .routes.agent_chatrooms import router as agent_chatrooms_router
from .routes.agents import router as agents_router
from .routes.auth import router as auth_router
from .routes.bot_messages import router as bot_messages_router
from .routes.chatrooms import router as chatrooms_router
from .routes.credits import router as credits_router
from .routes.maintenance import router as maintenance_router
from .routes.matching import router as matching_router
from .routes.payments import router as payments_router
from .routes.products import router as products_router
from .routes.pusher import router as pusher_router
from .routes.settings import router as settings_router
from .routes.users import router as users_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(agents_router)
api_router.include_router(agent_chatrooms_router)
api_router.include_router(auth_router)
api_router.include_router(bot_messages_router)
api_router.include_router(chatrooms_router)
api_router.include_router(credits_router)
api_router.include_router(maintenance_router)
api_router.include_router(matching_router)
api_router.include_router(payments_router)
api_router.include_router(products_router)
api_router.include_router(pusher_router)
api_router.include_router(settings_router)
api_router.include_router(telegram_router)
api_router.include_router(users_router)
