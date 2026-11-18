"""FastAPI application entry point for Automated Multi-Platform Posting System."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.schemas import HealthResponse, PostingRequest, PostingResponse
from app.services.posting_service import PostingService

# Setup application logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("multi_platform_posting")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for application startup and shutdown events."""
    logger.info("Initializing Automated Multi-Platform Posting System...")
    logger.info("Mock Mode: %s | Environment: %s", settings.mock_mode, settings.environment)
    yield
    logger.info("Shutting down Automated Multi-Platform Posting System...")


app = FastAPI(
    title="Automated Multi-Platform Posting System API",
    description=(
        "Production-ready FastAPI microservice that automatically validates a short message "
        "and publishes it concurrently across multiple third-party social media platforms and portals "
        "(Telegram, Discord, Slack, X/Twitter, Mastodon, and LinkedIn) with complete fault isolation."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Initialize posting service singleton
posting_service = PostingService(settings)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Provide clear, standardized error responses for Pydantic / schema validation failures."""
    errors = exc.errors()
    error_messages = []
    for err in errors:
        msg = err.get("msg", "")
        # Clean up Pydantic prefix if present
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, ") :]
        error_messages.append(msg)

    combined_error = " | ".join(error_messages) or "Invalid request input."
    logger.warning("Validation rejected request to %s: %s", request.url.path, combined_error)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Validation Error",
            "detail": combined_error,
            "results": [],
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle custom value error exceptions from domain validation."""
    logger.warning("Domain validation error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Validation Error",
            "detail": str(exc),
            "results": [],
        },
    )


@app.get(
    "/",
    tags=["Root"],
    summary="Root information endpoint",
    description="Returns service metadata and link to interactive API documentation.",
)
async def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "online",
        "documentation": "/docs",
        "supported_platforms": [p.platform_name for p in posting_service.platforms],
        "posting_endpoint": "POST /posting",
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check endpoint",
    description="Returns application health status, version, and platform configuration details.",
)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        app=settings.app_name,
        version=settings.app_version,
        platforms_supported=len(posting_service.platforms),
        mock_mode=settings.mock_mode,
    )


@app.post(
    "/posting",
    response_model=PostingResponse,
    status_code=status.HTTP_200_OK,
    tags=["Posting"],
    summary="Publish message across multiple platforms",
    description=(
        "Accepts a short message containing exactly one valid CTA link (max 200 characters). "
        "Automatically identifies and publishes the content concurrently across all supported platforms "
        "(Telegram, Discord, Slack, X/Twitter, Mastodon, and LinkedIn). "
        "Returns individual platform results including status, published URLs, timestamps, and error details."
    ),
)
async def post_message(payload: PostingRequest) -> PostingResponse:
    """
    Main API endpoint to broadcast a message to multiple platforms.
    """
    try:
        response = await posting_service.broadcast_message(payload.message)
        return response
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.exception("Unexpected server failure during broadcasting: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal server error occurred while processing the broadcast.",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
