"""Regression test: all AsyncSessionLocal usages outside request scope must be
mocked in the test suite to prevent cross-event-loop connection pool contamination.

Without these mocks, asyncpg connections acquired in one test's event loop cannot
be reused by the next test's event loop, causing:
  "Future <Future ...> attached to a different loop"
"""

from unittest.mock import MagicMock

import pytest


@pytest.mark.anyio
async def test_worker_asyncsession_is_mocked():
    """app.worker.AsyncSessionLocal must be mocked by an autouse fixture.

    FAILS before fix: the real AsyncSessionLocal is not patched, so calling
    it in tests would contaminate the connection pool across event loops.
    PASSES after fix: the autouse fixture replaces it with a MagicMock.
    """
    import app.worker as worker_module

    # The autouse fixture patches app.worker.AsyncSessionLocal.
    # When active, calling it returns a MagicMock (not a real session factory).
    instance = worker_module.AsyncSessionLocal()
    assert isinstance(instance, MagicMock), (
        "app.worker.AsyncSessionLocal must be mocked in tests. "
        "Add an autouse fixture in conftest.py that patches "
        "'app.worker.AsyncSessionLocal'. Without it, asyncpg connections "
        "bind to the test event loop and contaminate subsequent tests."
    )
