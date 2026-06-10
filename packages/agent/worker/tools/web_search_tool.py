import aiohttp
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from urllib.parse import urlencode


class Tool(ABC):
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    @abstractmethod
    async def run(self, input: Dict[str, Any], view) -> Any: ...


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web using DuckDuckGo HTML API (no API key required)."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "default": 5},
            "region": {"enum": ["wt-wt", "us-en", "uk-en", "cn-zh"], "default": "wt-wt"}
        },
        "required": ["query"]
    }

    def __init__(self, max_results: int = 5, timeout: int = 15):
        self.max_results = max_results
        self.timeout = timeout

    async def run(self, input, view):
        query = input["query"]
        max_results = input.get("max_results", self.max_results)
        region = input.get("region", "wt-wt")

        params = urlencode({"q": query, "kl": region})
        url = f"https://html.duckduckgo.com/html/?{params}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        return {"error": f"Search failed with status {resp.status}"}
                    html = await resp.text()
                    # Simple HTML parsing to extract results
                    results = self._parse_results(html, max_results)
                    return {"query": query, "results": results}
        except aiohttp.ClientError as e:
            return {"error": f"Network error: {str(e)}"}

    def _parse_results(self, html: str, max_results: int) -> list:
        """Simple regex-based extraction of search results from DuckDuckGo HTML."""
        import re
        results = []
        # Extract links with title and snippet
        pattern = r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
        for match in re.finditer(pattern, html, re.DOTALL):
            url = match.group(1)
            title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            if title and url:
                results.append({"title": title, "url": url})
                if len(results) >= max_results:
                    break
        return results
