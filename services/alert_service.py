import os
import sys
import httpx
import asyncio
from typing import Optional, Dict, Any
from loguru import logger

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

class AlertService:
    """
    Automated Error Crash Reporting & Webhook Alerting Service:
    - Integrates Sentry SDK for real-time error tracking when SENTRY_DSN is configured.
    - Dispatches asynchronous webhook alerts (Slack, Discord, PagerDuty, Telegram) upon critical exceptions.
    """
    def __init__(self) -> None:
        self.sentry_dsn = os.environ.get("SENTRY_DSN", "")
        self.webhook_url = os.environ.get("ALERT_WEBHOOK_URL", "")
        self._is_sentry_initialized = False

    def init_sentry(self) -> bool:
        if not self.sentry_dsn:
            logger.info("SENTRY_DSN not provided. Operating without Sentry crash reporting.")
            return False

        if SENTRY_AVAILABLE:
            try:
                sentry_sdk.init(
                    dsn=self.sentry_dsn,
                    environment=os.environ.get("ENVIRONMENT", "production"),
                    traces_sample_rate=0.2,
                    integrations=[FastApiIntegration()]
                )
                self._is_sentry_initialized = True
                logger.info(f"Sentry SDK initialized successfully for environment '{os.environ.get('ENVIRONMENT', 'production')}'.")
                return True
            except Exception as e:
                logger.error(f"Failed to initialize Sentry SDK: {e}")
                return False
        return False

    async def send_alert(self, title: str, error_message: str, correlation_id: Optional[str] = None, extra_context: Optional[Dict[str, Any]] = None) -> bool:
        """Dispatches an alert payload to configured Webhook URL."""
        if not self.webhook_url:
            logger.debug(f"Alert [{title}]: {error_message} (No ALERT_WEBHOOK_URL set)")
            return False

        payload = {
            "title": f"🚨 EduBot Alert: {title}",
            "error_message": error_message,
            "correlation_id": correlation_id or "N/A",
            "environment": os.environ.get("ENVIRONMENT", "production"),
            "extra_context": extra_context or {}
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(self.webhook_url, json=payload)
                if resp.status_code in [200, 201, 204]:
                    logger.info(f"Alert notification '{title}' successfully delivered to webhook.")
                    return True
                else:
                    logger.warning(f"Webhook alert returned HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Failed to send webhook alert '{title}': {e}")

        return False

alert_service = AlertService()
