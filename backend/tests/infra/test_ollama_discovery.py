from unittest.mock import AsyncMock, patch

import pytest

from app.infra.ollama import get_ollama_models


@pytest.mark.anyio
async def test_get_ollama_models_success():
    # 模拟 Ollama /api/tags 的响应
    mock_response = {
        "models": [
            {
                "name": "llama3:latest",
                "model": "llama3:latest",
                "modified_at": "2024-03-10T14:30:00Z",
                "size": 4661224679,
                "digest": "sha256:123",
            },
            {
                "name": "mistral:latest",
                "model": "mistral:latest",
                "modified_at": "2024-03-10T14:30:00Z",
                "size": 4109865159,
                "digest": "sha256:456",
            },
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(status_code=200, json=lambda: mock_response)

        models = await get_ollama_models()

        assert len(models) == 2
        assert "llama3:latest" in models
        assert "mistral:latest" in models


@pytest.mark.anyio
async def test_get_ollama_models_empty():
    mock_response = {"models": []}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(status_code=200, json=lambda: mock_response)

        models = await get_ollama_models()

        assert models == []


@pytest.mark.anyio
async def test_get_ollama_models_error():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(status_code=500)

        models = await get_ollama_models()

        # 发生错误时应返回空列表
        assert models == []
