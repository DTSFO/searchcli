from __future__ import annotations

import asyncio
import time
from pathlib import Path

import httpx

from .config import Config, config
from .errors import ConfigAppError, NetworkAppError, NotFoundAppError, UpstreamAppError, UsageAppError
from .planning import PlanningEngine, PlanningSession
from .providers.grok import GrokSearchProvider
from .providers.web import FirecrawlProvider, TavilyProvider
from .sources import merge_sources, new_session_id, split_answer_and_sources
from .state import StateRepository


def _config_error(exc: ValueError) -> ConfigAppError:
    return ConfigAppError(str(exc))


class SearchService:
    def __init__(self, settings: Config = config, state: StateRepository | None = None):
        self.config = settings
        self.state = state or StateRepository()

    async def search(self, query: str, platform: str = "", model: str = "", extra_sources: int = 0) -> dict:
        if not query.strip():
            raise UsageAppError("Query must not be empty")
        session_id = new_session_id()
        try:
            api_url, api_key = self.config.grok_api_url, self.config.grok_api_key
        except ValueError as exc:
            raise _config_error(exc) from exc
        effective_model = model or self.config.grok_model
        if model:
            models = await self.models()
            if models and model not in models:
                raise ConfigAppError(f"Invalid model: {model}", {"available_models": models})
        grok = GrokSearchProvider(api_url, api_key, effective_model)
        warnings: list[dict] = []

        async def optional(name: str, coro):
            try:
                return await coro
            except Exception as exc:
                warnings.append({"provider": name, "error": type(exc).__name__})
                return []

        tavily_count = extra_sources if extra_sources > 0 and self.config.tavily_api_key else 0
        firecrawl_count = 0
        if extra_sources > 0 and self.config.firecrawl_api_key:
            firecrawl_count = extra_sources
            tavily_count = 0
        tasks = [grok.search(query, platform)]
        if tavily_count:
            tasks.append(optional("tavily", TavilyProvider(self.config.tavily_api_url, self.config.tavily_api_key).search(query, tavily_count)))
        if firecrawl_count:
            tasks.append(optional("firecrawl", FirecrawlProvider(self.config.firecrawl_api_url, self.config.firecrawl_api_key).search(query, firecrawl_count)))
        try:
            results = await asyncio.gather(*tasks)
        except httpx.TimeoutException as exc:
            raise NetworkAppError("Grok request timed out") from exc
        except httpx.RequestError as exc:
            raise NetworkAppError("Grok network request failed") from exc
        except httpx.HTTPStatusError as exc:
            raise UpstreamAppError(f"Grok returned HTTP {exc.response.status_code}", {"status_code": exc.response.status_code}) from exc
        answer, grok_sources = split_answer_and_sources(results[0] or "")
        cited = {int(value) for value in __import__("re").findall(r"\[\[(\d+)\]\]", answer)}
        available = {item.get("citation_number") for item in grok_sources}
        missing = sorted(cited - available)
        if missing:
            warnings.append({"provider": "grok", "error": "missing_citations", "citation_numbers": missing})
        extra: list[dict] = []
        for provider_name, items in (("tavily", results[1] if tavily_count else []),
                                     ("firecrawl", results[-1] if firecrawl_count else [])):
            for item in items or []:
                url = (item.get("url") or "").strip()
                if url:
                    extra.append({"url": url, "title": item.get("title", ""),
                                  "description": item.get("content") or item.get("description", ""),
                                  "provider": provider_name})
        sources = merge_sources(grok_sources, extra)
        self.state.save("sources", session_id, sources)
        return {"session_id": session_id, "content": answer, "sources_count": len(sources), "warnings": warnings}

    def sources(self, session_id: str) -> dict:
        sources = self.state.load("sources", session_id)["data"]
        return {"session_id": session_id, "sources_count": len(sources), "sources": sources}

    async def models(self) -> list[str]:
        try:
            api_url, api_key = self.config.grok_api_url, self.config.grok_api_key
        except ValueError as exc:
            raise _config_error(exc) from exc
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{api_url.rstrip('/')}/models", headers={"Authorization": f"Bearer {api_key}"})
                response.raise_for_status()
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise UpstreamAppError("Models endpoint returned a non-JSON response") from exc
                return [item["id"] for item in payload.get("data", []) if isinstance(item, dict) and isinstance(item.get("id"), str)]
        except httpx.TimeoutException as exc:
            raise NetworkAppError("Model discovery timed out") from exc
        except httpx.RequestError as exc:
            raise NetworkAppError("Model discovery failed") from exc
        except httpx.HTTPStatusError as exc:
            raise UpstreamAppError(f"Models endpoint returned HTTP {exc.response.status_code}") from exc


class ContentService:
    def __init__(self, settings: Config = config):
        self.config = settings

    async def fetch(self, url: str) -> dict:
        warnings: list[dict] = []
        if self.config.tavily_api_key and self.config.tavily_enabled:
            try:
                content = await TavilyProvider(self.config.tavily_api_url, self.config.tavily_api_key).extract(url)
                if content:
                    return {"url": url, "content": content, "provider": "tavily", "warnings": warnings}
            except Exception as exc:
                warnings.append({"provider": "tavily", "error": type(exc).__name__})
        if self.config.firecrawl_api_key:
            try:
                attempts = self.config.retry_max_attempts
            except ValueError as exc:
                raise _config_error(exc) from exc
            content = await FirecrawlProvider(self.config.firecrawl_api_url, self.config.firecrawl_api_key).scrape(url, attempts)
            if content:
                return {"url": url, "content": content, "provider": "firecrawl", "warnings": warnings}
        if not self.config.tavily_api_key and not self.config.firecrawl_api_key:
            raise ConfigAppError("TAVILY_API_KEY and FIRECRAWL_API_KEY are not configured")
        raise UpstreamAppError("All content extraction providers failed", {"warnings": warnings})

    async def map(self, url: str, instructions: str, max_depth: int, max_breadth: int, limit: int, timeout: int) -> dict:
        return await TavilyProvider(self.config.tavily_api_url, self.config.tavily_api_key).map(
            url, instructions, max_depth, max_breadth, limit, timeout
        )


class ConfigService:
    def __init__(self, settings: Config = config):
        self.config = settings

    async def show(self, check: bool = False) -> dict:
        result = self.config.get_config_info()
        if check:
            started = time.monotonic()
            models = await SearchService(self.config).models()
            result["connection_test"] = {"status": "ok", "response_time_ms": round((time.monotonic() - started) * 1000, 2), "available_models": models}
        return result

    def import_env(self, source: Path) -> dict:
        try:
            return self.config.import_env_file(source)
        except OSError as exc:
            raise ConfigAppError(f"Unable to import environment file: {exc}") from exc


class PlanningService:
    def __init__(self, state: StateRepository | None = None):
        self.state = state or StateRepository()

    def process(self, phase: str, thought: str, session_id: str = "", is_revision: bool = False,
                confidence: float = 1.0, phase_data: dict | list | None = None) -> dict:
        target_id = session_id or new_session_id()
        with self.state.lock("planning", target_id):
            engine = PlanningEngine()
            if session_id:
                record = self.state.load("planning", session_id, refresh=False)
                engine.put_session(PlanningSession.from_dict(record["data"]))
            try:
                result = engine.process_phase(phase=phase, thought=thought, session_id=target_id,
                                              is_revision=is_revision, confidence=confidence, phase_data=phase_data)
            except ValueError as exc:
                raise UsageAppError(str(exc)) from exc
            session = engine.get_session(result["session_id"])
            if session is None:
                raise NotFoundAppError(f"Planning session '{result['session_id']}' not found")
            self.state.save("planning", session.session_id, session.to_dict())
            return result
