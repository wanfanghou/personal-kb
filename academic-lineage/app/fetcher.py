"""Safe fetching of academic homepage metadata for user-submitted URLs."""
import re
import ssl
import urllib.error
import urllib.request
from html.parser import HTMLParser

try:
    import certifi

    _CA_BUNDLE = certifi.where()
except ImportError:  # pragma: no cover
    _CA_BUNDLE = None

from .config import FETCH_MAX_BYTES, FETCH_MAX_REDIRECTS, FETCH_TIMEOUT_SECONDS
from .repositories import normalize_homepage_url

DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; AcademicLineage/1.0; local research tool)"


def _default_ssl_context():
    """Build an SSL context that prefers a bundled CA bundle.

    Some Windows machines carry malformed certificates in the system
    store, which makes ssl.create_default_context() fail with
    "[ASN1: NOT_ENOUGH_DATA] not enough data". Loading the CA bundle
    from certifi avoids reading the Windows store entirely.
    """
    if _CA_BUNDLE:
        return ssl.create_default_context(cafile=_CA_BUNDLE)
    return ssl.create_default_context()


def _build_default_opener():
    return urllib.request.build_opener(
        _LimitedRedirectHandler(),
        urllib.request.HTTPSHandler(context=_default_ssl_context()),
    )

_SEPARATORS = re.compile(r"\s*[|·•—–,;:]+\s*")
_SPACED_DASH = re.compile(r"\s+[-–]\s+")


def _candidate_from(source: str) -> str:
    first = _SEPARATORS.split(source)[0].strip()
    if first == source.strip():
        first = _SPACED_DASH.split(source)[0].strip()
    return first


def validate_url(url: str) -> str:
    """Validate and normalize a homepage URL; raises ValueError when unsafe."""
    return normalize_homepage_url(url)


class _MetadataParser(HTMLParser):
    """Minimal HTMLParser that captures title and common meta tags."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self.og_title = None
        self.author = None
        self.description = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._in_title = True
            return
        if tag != "meta":
            return
        prop = (attrs.get("property") or attrs.get("name") or "").strip().lower()
        content = attrs.get("content")
        if content is None:
            return
        if prop in ("og:title", "twitter:title") and self.og_title is None:
            self.og_title = content
        elif prop == "author" and self.author is None:
            self.author = content
        elif prop == "description" and self.description is None:
            self.description = content

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def _clean(text, limit: int = 500) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()[:limit]


def parse_html_metadata(html: str) -> dict:
    parser = _MetadataParser()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        pass

    title = _clean(parser.title)
    og_title = _clean(parser.og_title)
    author = _clean(parser.author)
    description = _clean(parser.description)

    candidate = author
    if not candidate:
        source = og_title or title
        if source:
            candidate = _candidate_from(source)

    return {
        "title": og_title or title,
        "candidate_name": candidate,
        "description": description,
    }


class _LimitedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, max_redirects: int = FETCH_MAX_REDIRECTS):
        super().__init__()
        self.max_redirects = max_redirects
        self._count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self._count += 1
        if self._count > self.max_redirects:
            raise urllib.error.HTTPError(req.full_url, code, "too many redirects", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def preview_person_url(url: str, opener=None) -> dict:
    """Fetch minimal metadata for a homepage URL. Never raises on network errors."""
    normalized_url = validate_url(url)
    result = {
        "normalized_url": normalized_url,
        "title": "",
        "candidate_name": "",
        "description": "",
        "http_status": None,
        "fetch_error": None,
    }
    try:
        if opener is None:
            opener = _build_default_opener()
        request = urllib.request.Request(
            normalized_url,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with opener.open(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            http_status = getattr(response, "status", None) or response.getcode() or 200
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and "html" not in content_type and "xhtml" not in content_type:
                result["http_status"] = http_status
                result["fetch_error"] = "not an HTML page"
                return result
            body = response.read(FETCH_MAX_BYTES + 1)
            if len(body) > FETCH_MAX_BYTES:
                result["http_status"] = http_status
                result["fetch_error"] = "response exceeds size limit"
                return result
            metadata = parse_html_metadata(body.decode("utf-8", errors="replace"))
            result.update(metadata)
            result["http_status"] = http_status
    except urllib.error.HTTPError as error:
        result["http_status"] = error.code
        result["fetch_error"] = f"HTTP error {error.code}"
    except urllib.error.URLError as error:
        result["fetch_error"] = str(error.reason or error)
    except Exception as error:  # timeouts, socket errors, etc.
        result["fetch_error"] = str(error) or type(error).__name__
    return result
