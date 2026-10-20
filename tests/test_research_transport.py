import os
from unittest import TestCase
from unittest.mock import patch, Mock
from urllib.error import HTTPError
from research_common.http import JsonGet, DataUnavailable, secret


class TransportTests(TestCase):
    def test_get_only_and_secret_redaction(self):
        client = JsonGet("https://api.the-odds-api.com")
        client._opener = Mock()
        client._opener.open.side_effect = HTTPError("https://example.com?key=secret", 401, "secret", {}, None)
        with self.assertRaises(DataUnavailable) as caught:
            client.get("/v4/sports", {"apiKey": "secret"})
        self.assertNotIn("secret", str(caught.exception))
        request = client._opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")

    def test_no_order_host_or_redirect(self):
        for host in ["https://api.alpaca.markets", "https://paper-api.alpaca.markets", "http://data.alpaca.markets"]:
            with self.assertRaises(ValueError):
                JsonGet(host)
        from research_common.http import NoRedirect
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com"))

    @patch("research_common.http.time.sleep")
    def test_bounded_rate_limit_retry(self, sleep):
        client = JsonGet("https://data.alpaca.markets")
        client._opener = Mock()
        client._opener.open.side_effect = HTTPError("url", 429, "Rate limited", {}, None)
        with self.assertRaises(DataUnavailable):
            client.get("/v2/stocks/bars", {})
        self.assertEqual(client._opener.open.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_credentials(self):
        with self.assertRaises(DataUnavailable):
            secret("ALPACA_API_KEY")
