import urllib.error

import pytest

from app.fetcher import parse_html_metadata, preview_person_url, validate_url


def test_metadata_prefers_og_title_and_author():
    html = """
    <html><head>
      <title>Fallback title</title>
      <meta property="og:title" content="Jane Doe | University">
      <meta name="author" content="Jane Doe">
      <meta name="description" content="Research profile">
    </head></html>
    """
    result = parse_html_metadata(html)
    assert result["title"] == "Jane Doe | University"
    assert result["candidate_name"] == "Jane Doe"
    assert result["description"] == "Research profile"


def test_metadata_falls_back_to_title_first_segment():
    html = "<html><head><title>Ada Lovelace - Homepage</title></head></html>"
    result = parse_html_metadata(html)
    assert result["title"] == "Ada Lovelace - Homepage"
    assert result["candidate_name"] == "Ada Lovelace"


def test_unsafe_url_is_rejected():
    with pytest.raises(ValueError, match="http or https"):
        validate_url("file:///secret.txt")


def test_javascript_url_is_rejected():
    with pytest.raises(ValueError, match="http or https"):
        validate_url("javascript:alert(1)")


def test_credentials_url_is_rejected():
    with pytest.raises(ValueError, match="credentials"):
        validate_url("https://user:pass@example.edu/jane")


def test_hostless_url_is_rejected():
    with pytest.raises(ValueError, match="hostname"):
        validate_url("https:///path-only")


class _FakeResponse:
    def __init__(self, body=b"<html><head><title>T</title></head></html>",
                 content_type="text/html; charset=utf-8", status=200):
        self._body = body
        self.headers = {"Content-Type": content_type}
        self.status = status

    def getcode(self):
        return self.status

    def read(self, size=-1):
        if size == -1:
            return self._body
        return self._body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeOpener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def open(self, request, timeout=None):
        if self.error is not None:
            raise self.error
        return self.response


def test_preview_returns_metadata_with_injected_opener():
    opener = _FakeOpener(_FakeResponse())
    result = preview_person_url("https://example.edu/jane", opener=opener)
    assert result["normalized_url"] == "https://example.edu/jane"
    assert result["title"] == "T"
    assert result["fetch_error"] is None
    assert result["http_status"] == 200


def test_preview_rejects_non_html_content_type():
    opener = _FakeOpener(_FakeResponse(content_type="application/pdf"))
    result = preview_person_url("https://example.edu/jane", opener=opener)
    assert "HTML" in result["fetch_error"]


def test_preview_reports_network_failure_without_raising():
    opener = _FakeOpener(error=urllib.error.URLError("connection refused"))
    result = preview_person_url("https://example.edu/jane", opener=opener)
    assert result["fetch_error"]
    assert result["normalized_url"] == "https://example.edu/jane"


def test_preview_reports_http_error_without_raising():
    opener = _FakeOpener(error=urllib.error.HTTPError(
        "https://example.edu/jane", 404, "not found", {}, None))
    result = preview_person_url("https://example.edu/jane", opener=opener)
    assert result["http_status"] == 404
    assert result["fetch_error"]
