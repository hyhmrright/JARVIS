from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.anyio
async def test_list_available_models_api(client):
    mock_ollama_models = ["llama3:latest", "mistral:latest"]

    with patch(
        "app.api.settings.get_ollama_models", AsyncMock(return_value=mock_ollama_models)
    ):
        resp = await client.get("/api/settings/models")

        assert resp.status_code == 200
        data = resp.json()
        assert "deepseek" in data
        assert "ollama" in data
        assert data["ollama"] == mock_ollama_models
