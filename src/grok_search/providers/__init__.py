from .base import BaseSearchProvider, SearchResult

__all__ = ["BaseSearchProvider", "SearchResult", "GrokSearchProvider"]


def __getattr__(name: str):
    if name == "GrokSearchProvider":
        from .grok import GrokSearchProvider
        globals()[name] = GrokSearchProvider
        return GrokSearchProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
