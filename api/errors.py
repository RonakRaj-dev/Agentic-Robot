from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from loguru import logger

class AppBaseException(Exception):
    """Base exception class for domain errors across Silicon_Project backend."""
    def __init__(
        self,
        message: str,
        code: str = "ERR_INTERNAL",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

class LLMDegradedError(AppBaseException):
    """Raised when external LLM APIs fail or circuit breakers trip."""
    def __init__(self, message: str = "LLM Service is currently degraded. Using fallback pipeline.") -> None:
        super().__init__(
            message=message,
            code="ERR_LLM_DEGRADED",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

class DatabaseUnavailableError(AppBaseException):
    """Raised when database connection fails without in-memory fallback."""
    def __init__(self, message: str = "Database service is temporarily unavailable.") -> None:
        super().__init__(
            message=message,
            code="ERR_DB_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

class ResourceNotFoundError(AppBaseException):
    """Raised when requested curriculum resource or chapter does not exist."""
    def __init__(self, message: str = "Requested resource not found.") -> None:
        super().__init__(
            message=message,
            code="ERR_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )

class ValidationError(AppBaseException):
    """Raised when request payload or parameters fail validation bounds."""
    def __init__(self, message: str = "Invalid request payload.") -> None:
        super().__init__(
            message=message,
            code="ERR_VALIDATION",
            status_code=status.HTTP_400_BAD_REQUEST
        )


from services.alert_service import alert_service

async def app_exception_handler(request: Request, exc: AppBaseException) -> JSONResponse:
    """Centralized JSON handler for custom application domain exceptions."""
    logger.warning(f"Domain exception on {request.url.path}: [{exc.code}] {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )

async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Centralized JSON handler catching raw unhandled exceptions and triggering alert service."""
    corr_id = getattr(request.state, "correlation_id", "N/A")
    logger.error(f"Unhandled exception on {request.url.path} [Request ID: {corr_id}]: {repr(exc)}")
    
    # Asynchronously dispatch error alert notification
    try:
        import asyncio
        asyncio.create_task(alert_service.send_alert(
            title=f"Unhandled Exception on {request.url.path}",
            error_message=str(exc),
            correlation_id=corr_id,
            extra_context={"path": str(request.url.path), "method": request.method}
        ))
    except Exception:
        pass

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "ERR_INTERNAL_SERVER",
                "message": f"An unexpected error occurred: {repr(exc)}",
                "correlation_id": corr_id,
                "detail": str(exc)
            }
        }
    )
