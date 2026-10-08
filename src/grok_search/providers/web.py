from __future__ import annotations

import httpx

from ..errors import ConfigAppError, NetworkAppError, UpstreamAppError


def _raise_http(exc: Exception, provider: str) -> None:
    if isinstance(exc, httpx.TimeoutException):
        raise NetworkAppError(f"{provider} request timed out") from exc
    if isinstance(exc, httpx.RequestError):
        raise NetworkAppError(f"{provider} network request failed") from exc
    if isinstance(exc, httpx.HTTPStatusError):
        raise UpstreamAppError(
            f"{provider} returned HTTP {exc.response.status_code}",
            {"status_code": exc.response.status_code},
        ) from exc
    raise exc


class TavilyProvider:
    def __init__(self, api_url: str, api_key: str | None):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ConfigAppError("TAVILY_API_KEY is not configured")
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def search(self, query: str, max_results: int) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    f"{self.api_url}/search", headers=self._headers(),
                    json={"query": query, "max_results": max_results, "search_depth": "advanced",
                          "include_raw_content": False, "include_answer": False},
                )
                response.raise_for_status()
                return response.json().get("results", []) or []
        except Exception as exc:
            _raise_http(exc, "Tavily")
            raise

    async def extract(self, url: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_url}/extract", headers=self._headers(),
                    json={"urls": [url], "format": "markdown"},
                )
                response.raise_for_status()
                results = response.json().get("results", []) or []
                content = results[0].get("raw_content", "") if results else ""
                return content if content.strip() else None
        except Exception as exc:
            _raise_http(exc, "Tavily")
            raise

    async def map(self, url: str, instructions: str, max_depth: int, max_breadth: int,
                  limit: int, timeout: int = 30) -> dict:
        body: dict = {"url": url, "max_depth": max_depth, "max_breadth": max_breadth,
                      "limit": limit, "timeout": timeout}
        if instructions:
            body["instructions"] = instructions
        try:
            async with httpx.AsyncClient(timeout=float(timeout + 10)) as client:
                response = await client.post(f"{self.api_url}/map", headers=self._headers(), json=body)
                response.raise_for_status()
                data = response.json()
                return {"base_url": data.get("base_url", ""), "results": data.get("results", []),
                        "response_time": data.get("response_time", 0)}
        except Exception as exc:
            _raise_http(exc, "Tavily")
            raise


class FirecrawlProvider:
    def __init__(self, api_url: str, api_key: str | None):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ConfigAppError("FIRECRAWL_API_KEY is not configured")
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def search(self, query: str, limit: int) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(f"{self.api_url}/search", headers=self._headers(),
                                             json={"query": query, "limit": limit})
                response.raise_for_status()
                return response.json().get("data", {}).get("web", []) or []
        except Exception as exc:
            _raise_http(exc, "Firecrawl")
            raise

    async def scrape(self, url: str, attempts: int) -> str | None:
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    response = await client.post(
                        f"{self.api_url}/scrape", headers=self._headers(),
                        json={"url": url, "formats": ["markdown"], "timeout": 60000,
                              "waitFor": (attempt + 1) * 1500},
                    )
                    response.raise_for_status()
                    content = response.json().get("data", {}).get("markdown", "")
                    if content.strip():
                        return content
            except Exception as exc:
                _raise_http(exc, "Firecrawl")
        return None
