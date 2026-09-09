"""Retry decorators for MinIO, MongoDB, and extraction operations."""

import logging
from typing import Callable
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
    retry_if_exception_type,
    before_sleep_log,
)
from core.exceptions import MinIOUploadError, MongoWriteError, ExtractionError

logger = logging.getLogger(__name__)

MINIO_RETRY_CONFIG = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=1, max=10),
    "retry": retry_if_exception_type((MinIOUploadError, ConnectionError, TimeoutError)),
    "before_sleep": before_sleep_log(logger, logging.WARNING),
    "reraise": True,
}

MONGO_RETRY_CONFIG = {
    "stop": stop_after_attempt(3),
    "wait": wait_fixed(1),
    "retry": retry_if_exception_type((MongoWriteError, ConnectionError)),
    "before_sleep": before_sleep_log(logger, logging.WARNING),
    "reraise": True,
}

EXTRACTION_RETRY_CONFIG = {
    "stop": stop_after_attempt(2),
    "wait": wait_fixed(2),
    "retry": retry_if_exception_type((ExtractionError, TimeoutError)),
    "before_sleep": before_sleep_log(logger, logging.WARNING),
    "reraise": True,
}


def with_minio_retry(func: Callable) -> Callable:
    return retry(**MINIO_RETRY_CONFIG)(func)


def with_mongo_retry(func: Callable) -> Callable:
    return retry(**MONGO_RETRY_CONFIG)(func)


def with_extraction_retry(func: Callable) -> Callable:
    return retry(**EXTRACTION_RETRY_CONFIG)(func)
