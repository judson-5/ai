"""Fixed-host GET-only transport. Errors never include URLs or credentials."""
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler


class DataUnavailable(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def secret(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise DataUnavailable(f"Missing environment variable: {name}")
    return value


class JsonGet:
    HOSTS = {"https://data.alpaca.markets", "https://api.the-odds-api.com"}

    def __init__(self, host, headers=None):
        if host not in self.HOSTS:
            raise ValueError("Unapproved data host")
        self.host = host
        self._headers = dict(headers or {})
        self._opener = build_opener(NoRedirect())

    def get(self, path, params):
        if not path.startswith("/") or ".." in path or "?" in path:
            raise ValueError("Invalid data path")
        request = Request(self.host + path + "?" + urlencode(params),
                          headers=self._headers, method="GET")
        for attempt in range(3):
            try:
                with self._opener.open(request, timeout=20) as response:
                    raw = response.read(20_000_001)
                    if len(raw) > 20_000_000:
                        raise DataUnavailable("Provider response too large")
                    def reject_constant(_):
                        raise ValueError("Nonfinite provider JSON")
                    return json.loads(raw, parse_constant=reject_constant)
            except HTTPError as error:
                if error.code in {429, 500, 502, 503, 504} and attempt < 2:
                    time.sleep(0.25 * 2**attempt)
                    continue
                raise DataUnavailable(f"Data provider HTTP {error.code}") from None
            except (URLError, OSError, ValueError):
                raise DataUnavailable("Data provider unavailable or invalid JSON") from None
        raise DataUnavailable("Data provider retry limit reached")
