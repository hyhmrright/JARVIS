"""Unit tests for custom Prometheus metrics instrumentation."""

from prometheus_client import REGISTRY


def test_metrics_singletons_registered():
    """All custom metric names are registered in the Prometheus default registry."""
    names = {m.name for m in REGISTRY.collect()}
    assert "jarvis_cron_executions_total" in names
    assert "jarvis_rag_retrieval_duration_seconds" in names
    assert "jarvis_llm_requests_total" in names
    assert "jarvis_arq_queue_depth" in names


def test_cron_counter_labels():
    """cron_executions_total accepts the expected label values."""
    from app.core.metrics import cron_executions_total

    before = cron_executions_total.labels(status="fired")._value.get()
    cron_executions_total.labels(status="fired").inc()
    after = cron_executions_total.labels(status="fired")._value.get()
    assert after == before + 1.0


def test_rag_histogram_records_observation():
    """rag_retrieval_duration_seconds accepts float observations."""
    from app.core.metrics import rag_retrieval_duration_seconds

    rag_retrieval_duration_seconds.observe(0.123)
    rag_retrieval_duration_seconds.observe(1.5)


def test_llm_counter_labels():
    """llm_requests_total accepts provider, model, status labels."""
    from app.core.metrics import llm_requests_total

    before = llm_requests_total.labels(
        provider="deepseek", model="deepseek-chat", status="success"
    )._value.get()
    llm_requests_total.labels(
        provider="deepseek", model="deepseek-chat", status="success"
    ).inc()
    after = llm_requests_total.labels(
        provider="deepseek", model="deepseek-chat", status="success"
    )._value.get()
    assert after == before + 1.0


def test_arq_queue_depth_gauge():
    """arq_queue_depth Gauge accepts set() updates."""
    from app.core.metrics import arq_queue_depth

    arq_queue_depth.set(42)
    assert arq_queue_depth._value.get() == 42.0
    arq_queue_depth.set(0)
    assert arq_queue_depth._value.get() == 0.0
