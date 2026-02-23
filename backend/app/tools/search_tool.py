import httpx
from langchain_core.tools import tool


@tool
async def web_search(query: str) -> str:
    """Search the internet for up-to-date information. query is the search term."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1},
            timeout=10.0,
        )
    data = resp.json()
    abstract = data.get("AbstractText", "")
    related = [r.get("Text", "") for r in data.get("RelatedTopics", [])[:3]]
    return abstract or "\n".join(related) or "No results found."
