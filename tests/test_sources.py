from grok_search.sources import has_uncited_content, merge_sources


def test_merge_sources_normalizes_equivalent_urls():
    sources = merge_sources(
        [{"url": "HTTPS://Example.COM:443/docs/", "title": "first"}],
        [{"url": "https://example.com/docs#section"}],
        [{"url": "https://example.com/other"}],
    )
    assert [item["url"] for item in sources] == ["HTTPS://Example.COM:443/docs/", "https://example.com/other"]


def test_uncited_content_detection_is_conservative():
    assert has_uncited_content("This factual paragraph contains enough natural language words to make several concrete claims about a product release and its documented behavior without attaching any source citation at all.")
    assert not has_uncited_content("Short answer.")
    assert not has_uncited_content("```python\nprint('a long code block with many words but no factual prose')\n```")
    assert not has_uncited_content("A sufficiently long cited explanation with many factual words and a valid source marker [[1]] attached to the conclusion.")
