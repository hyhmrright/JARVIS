import os

import pytest

from app.core.config import settings


@pytest.mark.skipif(
    not os.getenv("LANGCHAIN_API_KEY"), reason="LangSmith API key not found"
)
def test_basic_eval_suite():
    """
    Placeholder for LangSmith Automated Evaluations.
    In a real scenario, this would use langsmith.evaluate() against a dataset
    to verify Agent logic and RAG retrieval accuracy.
    """
    assert settings.langchain_tracing_v2 in ["true", "false"]
    # This establishes the entry point for automated eval tests.
