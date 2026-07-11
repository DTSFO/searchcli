import pytest

from grok_search.services import ContentService, SearchService
from grok_search.state import StateRepository


class FakeConfig:
    grok_api_url = "https://grok.test/v1"
    grok_api_key = "secret"
    grok_model = "model"
    tavily_api_url = "https://tavily.test"
    tavily_api_key = "tavily-secret"
    tavily_enabled = True
    firecrawl_api_url = "https://firecrawl.test"
    firecrawl_api_key = "firecrawl-secret"
    retry_max_attempts = 2
    retry_multiplier = 1
    retry_max_wait = 10


@pytest.mark.asyncio
async def test_search_persists_sources_and_isolates_optional_failure(tmp_path, monkeypatch):
    async def fake_grok(self, query, platform="", min_results=3, max_results=10, ctx=None):
        return "Answer\n\nSources:\n- [Official](https://example.com)"

    async def failed_firecrawl(self, query, limit):
        raise RuntimeError("optional failure")

    monkeypatch.setattr("grok_search.services.GrokSearchProvider.search", fake_grok)
    monkeypatch.setattr("grok_search.services.FirecrawlProvider.search", failed_firecrawl)
    service = SearchService(FakeConfig(), StateRepository(tmp_path))
    result = await service.search("query", extra_sources=2)
    assert result["content"] == "Answer"
    assert result["sources_count"] == 1
    assert result["warnings"] == [{"provider": "firecrawl", "error": "RuntimeError"}]
    assert service.sources(result["session_id"])["sources"][0]["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_search_reports_unresolved_numbered_citations(tmp_path, monkeypatch):
    async def fake_grok(self, query, platform="", min_results=3, max_results=10, ctx=None):
        return "Claims [[1]] and [[2]].\n\nSources:\n1. [One](https://one.test)"

    monkeypatch.setattr("grok_search.services.GrokSearchProvider.search", fake_grok)
    service = SearchService(FakeConfig(), StateRepository(tmp_path))
    result = await service.search("query")
    assert result["warnings"] == [{"provider": "grok", "error": "missing_citations", "citation_numbers": [2]}]
    sources = service.sources(result["session_id"])["sources"]
    assert sources == [{"url": "https://one.test", "citation_number": 1, "title": "One"}]


@pytest.mark.asyncio
async def test_search_rejects_blank_query_before_provider(tmp_path, monkeypatch):
    called = False
    async def fake_grok(*args, **kwargs):
        nonlocal called
        called = True
    monkeypatch.setattr("grok_search.services.GrokSearchProvider.search", fake_grok)
    with pytest.raises(Exception, match="Query must not be empty"):
        await SearchService(FakeConfig(), StateRepository(tmp_path)).search("  ")
    assert called is False


@pytest.mark.asyncio
async def test_fetch_falls_back_to_firecrawl(monkeypatch):
    async def failed_extract(self, url):
        raise RuntimeError("tavily failed")

    async def firecrawl_content(self, url, attempts):
        return "# Example"

    monkeypatch.setattr("grok_search.services.TavilyProvider.extract", failed_extract)
    monkeypatch.setattr("grok_search.services.FirecrawlProvider.scrape", firecrawl_content)
    result = await ContentService(FakeConfig()).fetch("https://example.com")
    assert result["provider"] == "firecrawl"
    assert result["content"] == "# Example"
    assert result["warnings"][0]["provider"] == "tavily"


@pytest.mark.asyncio
async def test_map_forwards_bounds(monkeypatch):
    async def fake_map(self, url, instructions, max_depth, max_breadth, limit, timeout):
        return {"base_url": url, "results": ["https://example.com/docs"], "response_time": 1}

    monkeypatch.setattr("grok_search.services.TavilyProvider.map", fake_map)
    result = await ContentService(FakeConfig()).map("https://example.com", "docs", 2, 10, 20, 30)
    assert result["results"] == ["https://example.com/docs"]
