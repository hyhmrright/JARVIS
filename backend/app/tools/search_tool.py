import httpx
from langchain_core.tools import tool


@tool
async def web_search(query: str) -> str:
    """Search using DuckDuckGo Instant Answer API.

    Note: This API returns Wikipedia-style abstracts and related topics only.
    It does NOT perform general web search. Most queries will return empty results.
    query is the search term.
    """
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
