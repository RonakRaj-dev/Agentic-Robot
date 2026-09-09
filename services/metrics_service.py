import time
import asyncio
from typing import Dict, Any, Optional
from loguru import logger

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"

class MetricsService:
    """
    Real-time Prometheus Metrics Exporter & Token Cost Tracker:
    - HTTP throughput & latency histograms.
    - Groq LLM Token consumption counters (prompt vs completion).
    - Real-time LLM cost tracking in USD ($).
    - Multi-agent execution latency histograms.
    """
    # Groq Model Pricing Rates (USD per 1M tokens)
    MODEL_PRICING = {
        "llama-3.3-70b-versatile": {"prompt": 0.59 / 1_000_000, "completion": 0.79 / 1_000_000},
        "llama-3.1-8b-instant": {"prompt": 0.05 / 1_000_000, "completion": 0.08 / 1_000_000},
        "meta-llama/llama-4-scout-17b-16e-instruct": {"prompt": 0.20 / 1_000_000, "completion": 0.30 / 1_000_000},
        "default": {"prompt": 0.20 / 1_000_000, "completion": 0.30 / 1_000_000}
    }

    def __init__(self) -> None:
        self._in_memory_metrics = {
            "http_requests_total": 0,
            "llm_prompt_tokens_total": 0,
            "llm_completion_tokens_total": 0,
            "llm_cost_dollars_total": 0.0,
            "agent_executions_total": 0
        }
        self._lock = asyncio.Lock()

        if PROMETHEUS_AVAILABLE:
            self.http_requests_counter = Counter(
                "edubot_http_requests_total",
                "Total HTTP requests handled by endpoint and status code",
                ["method", "endpoint", "status_code"]
            )
            self.http_latency_histogram = Histogram(
                "edubot_http_request_duration_seconds",
                "HTTP request duration in seconds",
                ["method", "endpoint"]
            )
            self.llm_tokens_counter = Counter(
                "edubot_llm_tokens_total",
                "Total LLM tokens consumed",
                ["model", "token_type"]
            )
            self.llm_cost_counter = Counter(
                "edubot_llm_cost_dollars_total",
                "Estimated cumulative USD cost of LLM inference",
                ["model"]
            )
            self.agent_latency_histogram = Histogram(
                "edubot_agent_execution_seconds",
                "Multi-agent execution duration in seconds",
                ["agent_name"]
            )

    def record_http_request(self, method: str, endpoint: str, status_code: int, duration_seconds: float) -> None:
        self._in_memory_metrics["http_requests_total"] += 1
        if PROMETHEUS_AVAILABLE:
            try:
                self.http_requests_counter.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
                self.http_latency_histogram.labels(method=method, endpoint=endpoint).observe(duration_seconds)
            except Exception as e:
                logger.warning(f"Error recording Prometheus HTTP metrics: {e}")

    def record_llm_usage(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Records prompt and completion token counts and calculates estimated USD cost.
        Returns: estimated_cost_usd (float)
        """
        rates = self.MODEL_PRICING.get(model, self.MODEL_PRICING["default"])
        cost = (prompt_tokens * rates["prompt"]) + (completion_tokens * rates["completion"])

        self._in_memory_metrics["llm_prompt_tokens_total"] += prompt_tokens
        self._in_memory_metrics["llm_completion_tokens_total"] += completion_tokens
        self._in_memory_metrics["llm_cost_dollars_total"] += cost

        if PROMETHEUS_AVAILABLE:
            try:
                self.llm_tokens_counter.labels(model=model, token_type="prompt").inc(prompt_tokens)
                self.llm_tokens_counter.labels(model=model, token_type="completion").inc(completion_tokens)
                self.llm_cost_counter.labels(model=model).inc(cost)
            except Exception as e:
                logger.warning(f"Error recording Prometheus LLM metrics: {e}")

        logger.info(f"LLM Usage Recorded [{model}]: {prompt_tokens} prompt + {completion_tokens} completion tokens = ${cost:.6f} USD")
        return cost

    def record_agent_execution(self, agent_name: str, duration_seconds: float) -> None:
        self._in_memory_metrics["agent_executions_total"] += 1
        if PROMETHEUS_AVAILABLE:
            try:
                self.agent_latency_histogram.labels(agent_name=agent_name).observe(duration_seconds)
            except Exception as e:
                logger.warning(f"Error recording Prometheus agent metrics: {e}")

    def export_metrics(self) -> str:
        """Exports metrics payload in Prometheus text exposition format."""
        if PROMETHEUS_AVAILABLE:
            try:
                return generate_latest().decode("utf-8")
            except Exception as e:
                logger.error(f"Error generating Prometheus payload: {e}")

        # Fallback to custom Prometheus format text
        lines = [
            "# HELP edubot_http_requests_total Total HTTP requests handled",
            "# TYPE edubot_http_requests_total counter",
            f"edubot_http_requests_total {self._in_memory_metrics['http_requests_total']}",
            "# HELP edubot_llm_prompt_tokens_total Cumulative prompt tokens",
            "# TYPE edubot_llm_prompt_tokens_total counter",
            f"edubot_llm_prompt_tokens_total {self._in_memory_metrics['llm_prompt_tokens_total']}",
            "# HELP edubot_llm_completion_tokens_total Cumulative completion tokens",
            "# TYPE edubot_llm_completion_tokens_total counter",
            f"edubot_llm_completion_tokens_total {self._in_memory_metrics['llm_completion_tokens_total']}",
            "# HELP edubot_llm_cost_dollars_total Estimated cumulative LLM inference USD cost",
            "# TYPE edubot_llm_cost_dollars_total counter",
            f"edubot_llm_cost_dollars_total {self._in_memory_metrics['llm_cost_dollars_total']:.6f}",
        ]
        return "\n".join(lines) + "\n"

metrics_service = MetricsService()
