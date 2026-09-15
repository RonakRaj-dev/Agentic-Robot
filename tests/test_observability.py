import os
os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"

import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import asyncio
from services.metrics_service import metrics_service
from services.alert_service import alert_service

def test_prometheus_metrics_recording_and_token_cost_calculation():
    # 1. Test LLM usage recording and cost calculation
    cost = metrics_service.record_llm_usage(
        model="llama-3.3-70b-versatile",
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000
    )
    # 1M prompt ($0.59) + 1M completion ($0.79) = $1.38
    assert round(cost, 2) == 1.38

    # 2. Test HTTP request metric recording
    metrics_service.record_http_request(method="GET", endpoint="/metrics", status_code=200, duration_seconds=0.015)

    # 3. Test Prometheus exposition output
    metrics_text = metrics_service.export_metrics()
    assert "edubot_http_requests_total" in metrics_text
    assert "edubot_llm_cost_dollars_total" in metrics_text

@pytest.mark.asyncio
async def test_alert_service_webhook_fallback():
    # Test sending alert without webhook URL (graceful logging fallback)
    alert_service.webhook_url = ""
    result = await alert_service.send_alert(
        title="Test Critical Error",
        error_message="Test error message payload",
        correlation_id="req_test12345"
    )
    assert result is False

if __name__ == "__main__":
    test_prometheus_metrics_recording_and_token_cost_calculation()
    asyncio.run(test_alert_service_webhook_fallback())
    print("✅ ALL OBSERVABILITY, METRICS & ALERTING TESTS PASSED 100% SUCCESS!")
