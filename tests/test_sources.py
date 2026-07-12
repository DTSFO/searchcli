from grok_search.sources import has_uncited_content, merge_sources


def test_merge_sources_normalizes_equivalent_urls():
    sources = merge_sources(
        [{"url": "HTTPS://Example.COM:443/docs/", "title": "first"}],
        [{"url": "https://example.com/docs#section"}],
        [{"url": "https://example.com/other"}],
    )
    assert [item["url"] for item in sources] == ["HTTPS://Example.COM:443/docs/", "https://example.com/other"]


def test_merge_sources_normalizes_root_slash():
    sources = merge_sources([{"url": "https://example.com"}], [{"url": "https://example.com/"}])
    assert sources == [{"url": "https://example.com"}]


def test_uncited_content_detection_is_conservative():
    assert has_uncited_content("This factual paragraph contains enough natural language words to make several concrete claims about a product release and its documented behavior without attaching any source citation at all.")
    assert not has_uncited_content("Short answer.")
    assert not has_uncited_content("```python\nprint('a long code block with many words but no factual prose')\n```")
    assert not has_uncited_content("A sufficiently long cited explanation with many factual words and a valid source marker [[1]] attached to the conclusion.")


def test_uncited_content_detects_partially_cited_prose():
    text = (
        "This first paragraph contains enough factual explanation about a documented release and has a source marker attached to its conclusion [[1]].\n\n"
        "This second paragraph contains another substantial factual explanation about version behavior compatibility dates and operational changes but provides no citation marker for any of those claims."
    )
    assert has_uncited_content(text)


def test_uncited_content_supports_chinese_thresholds():
    assert has_uncited_content("这个版本已经修改了默认执行流程，并且调整了多个配置字段的含义，同时改变了会话持久化和错误分类的具体行为。")
    assert not has_uncited_content("这是简短说明。")
    assert not has_uncited_content("```text\n这是很长的中文代码块内容，不应被当作需要引用的事实正文，即使字符数量超过阈值。\n```")
