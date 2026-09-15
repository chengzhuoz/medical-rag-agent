from io import BytesIO

from django.conf import settings

from qa.web_search import search_web


class _FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_web_search_parses_safe_public_result(monkeypatch):
    html = b'''<article><a class="result__a" href="https://www.nmpa.gov.cn/example">NMPA notice</a><a class="result__snippet">Official update</a></article>'''
    monkeypatch.setattr("qa.web_search.urlopen", lambda *_args, **_kwargs: _FakeResponse(html))
    monkeypatch.setattr(settings, "WEB_SEARCH_ENABLED", True)

    result = search_web("medical device regulation", max_results=99)

    assert result["ok"] is True
    assert result["provider"] == "duckduckgo_html"
    assert result["results"] == [{"title": "NMPA notice", "url": "https://www.nmpa.gov.cn/example", "snippet": "Official update", "domain": "www.nmpa.gov.cn"}]


def test_web_search_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_ENABLED", False)

    result = search_web("any query")

    assert result == {"ok": False, "error": "web_search_disabled", "results": []}
