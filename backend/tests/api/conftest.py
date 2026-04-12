"""API-layer conftest: fixtures only relevant to tests/api/."""


# _suppress_chat_async_session was removed because it was redundant with the
# root conftest's mock_background_db_tasks and was causing AttributeError
# due to app.api.chat.routes no longer importing AsyncSessionLocal.
