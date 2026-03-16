"""Custom Prometheus metrics for JARVIS application observability.

Import the singletons from this module and call them directly — do NOT
re-instantiate them elsewhere (prometheus-client raises on duplicate names).
"""

from prometheus_client import Counter, Gauge, Histogram

cron_executions_total = Counter(
    "jarvis_cron_executions_total",
    "Total number of cron job executions by outcome",
    labelnames=["status"],
)

rag_retrieval_duration_seconds = Histogram(
    "jarvis_rag_retrieval_duration_seconds",
    "End-to-end RAG retrieval latency in seconds",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

llm_requests_total = Counter(
    "jarvis_llm_requests_total",
    "Total LLM invocations by provider, model, and outcome",
    labelnames=["provider", "model", "status"],
)

arq_queue_depth = Gauge(
    "jarvis_arq_queue_depth",
    "Number of jobs currently queued in the ARQ Redis queue",
)
