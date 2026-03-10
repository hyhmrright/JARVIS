import httpx

from app.core.config import settings


async def get_ollama_models() -> list[str]:
    """从本地 Ollama API 获取已下载的模型名称列表。"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code != 200:
                return []

            data = resp.json()
            models = data.get("models", [])
            # 提取模型名称
            return [m.get("name") for m in models if m.get("name")]
    except (httpx.RequestError, ValueError):
        # 发生网络错误或解析 JSON 失败
        return []
