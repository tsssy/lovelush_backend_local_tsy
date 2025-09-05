"""FastAPI application entry point with DDD architecture."""

import traceback
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config.settings import settings
from app.core.exceptions.exceptions import BaseCustomException
from app.core.logging import get_logger
from app.core.responses import ResponseHelper
from app.core.startup import app_startup_service
from app.interfaces.api.v1.api import api_router

logger = get_logger(__name__)


class ExceptionLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to ensure all exceptions are properly logged with full tracebacks."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except BaseCustomException as exc:
            # Log custom exceptions with full context
            logger.error(
                f"Custom exception occurred: {exc.message} | "
                f"Status: {exc.status_code} | "
                f"API Code: {exc.api_code} | "
                f"URL: {request.url} | "
                f"Method: {request.method}",
                exc_info=True,
            )
            # Return proper JSON response for custom exceptions
            return JSONResponse(
                status_code=exc.status_code,
                content={"code": exc.api_code, "msg": exc.message, "data": exc.details},
            )
        except HTTPException as exc:
            # Log HTTP exceptions with full context
            logger.error(
                f"HTTP exception occurred: {exc.detail} | "
                f"Status: {exc.status_code} | "
                f"URL: {request.url} | "
                f"Method: {request.method}",
                exc_info=True,
            )
            # Return proper JSON response for HTTP exceptions
            return JSONResponse(
                status_code=exc.status_code,
                content={"code": exc.status_code, "msg": exc.detail, "data": None},
            )
        except Exception as exc:
            # Log all other exceptions with full traceback
            logger.error(
                f"Unhandled exception occurred: {str(exc)} | "
                f"Type: {type(exc).__name__} | "
                f"URL: {request.url} | "
                f"Method: {request.method} | "
                f"Traceback: {traceback.format_exc()}",
                exc_info=True,
            )

            # Return a generic 500 error response
            # Include more details in debug mode
            if settings.debug:
                error_detail = {
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "traceback": traceback.format_exc().split("\n"),
                }
            else:
                error_detail = None

            return JSONResponse(
                status_code=500,
                content={
                    "code": 500,
                    "msg": (
                        "Internal Server Error"
                        if not settings.debug
                        else f"{type(exc).__name__}: {str(exc)}"
                    ),
                    "data": error_detail,
                },
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting FastAPI application...")
    await app_startup_service.initialize_application()
    yield
    # Shutdown
    logger.info("Shutting down FastAPI application...")
    await app_startup_service.shutdown_application()


def create_application() -> FastAPI:
    """Create FastAPI application with all configurations."""
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        root_path=settings.app_root_path,
    )

    # Add global exception handlers
    @application.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions with consistent response format."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.status_code, "msg": exc.detail, "data": None},
        )

    @application.exception_handler(BaseCustomException)
    async def custom_exception_handler(request: Request, exc: BaseCustomException):
        """Handle custom exceptions with consistent response format."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.api_code, "msg": exc.message, "data": exc.details},
        )

    # Add exception logging middleware FIRST to catch all exceptions
    application.add_middleware(ExceptionLoggingMiddleware)

    # Add CORS middleware with development-friendly settings
    cors_origins = settings.cors_origins
    if settings.debug:
        # In debug mode, be more permissive with CORS
        cors_origins = ["*"]  # Force allow all origins for debugging

    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,  # Disable credentials so wildcard origins (*) work reliably in WebView
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    application.include_router(api_router)

    return application


app = create_application()


@app.get("/")
async def root():
    """Root endpoint."""
    return ResponseHelper.success(
        data={
            "app_name": settings.app_name,
            "version": settings.app_version,
            "docs_url": "/docs",
            "redoc_url": "/redoc",
        },
        msg=f"Welcome to {settings.app_name}",
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return ResponseHelper.success(
        data={
            "status": "healthy",
            "app_name": settings.app_name,
            "version": settings.app_version,
        },
        msg="Application is healthy",
    )


@app.get("/cors-test")
async def cors_test():
    """CORS test endpoint to verify cross-origin requests work."""
    return ResponseHelper.success(
        data={
            "cors": "enabled",
            "debug": settings.debug,
            "message": "If you can see this from your HTML page, CORS is working!",
            "timestamp": "2025-08-25T12:00:00Z",
        },
        msg="CORS test successful",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=9000,
        reload=settings.debug,
    )
