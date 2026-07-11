import json

import pytest

from grok_search.providers.grok import GrokSearchProvider


class FakeResponse:
    async def aiter_lines(self):
        chunks = [
            {"choices": [{"delta": {"content": "Claim [[1]]."}}]},
            {"choices": [{"delta": {}, "citations": [{"url": "https://example.test", "title": "Example"}]}]},
        ]
        for chunk in chunks:
            yield "data: " + json.dumps(chunk)
        yield "data: [DONE]"


@pytest.mark.asyncio
async def test_stream_parser_preserves_citation_metadata(monkeypatch):
    async def noop(*args, **kwargs):
        return None
    monkeypatch.setattr("grok_search.providers.grok.log_info", noop)
    text = await GrokSearchProvider("https://grok.test", "secret")._parse_streaming_response(FakeResponse())
    assert "Claim [[1]]." in text
    assert "1. [Example](https://example.test)" in text
