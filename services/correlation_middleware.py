import uuid
from typing import Callable
from loguru import logger
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Correlation ID Context Middleware:
    - Extracts 'X-Request-ID' from incoming request headers or generates a unique UUID4.
    - Injects 'X-Request-ID' into loguru contextual logging and response headers.
    """
    HEADER_NAME = "X-Request-ID"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract or generate correlation ID
        correlation_id = request.headers.get(self.HEADER_NAME) or f"req_{uuid.uuid4().hex[:16]}"
        
        # Store in request state for downstream handlers
        request.state.correlation_id = correlation_id

        # Contextualize loguru logger for all logs generated within this request thread
        with logger.contextualize(request_id=correlation_id):
            response = await call_next(request)
            response.headers[self.HEADER_NAME] = correlation_id
            return response
