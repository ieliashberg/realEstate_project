"""Offline security and compatibility smoke tests for the dependency refresh.

Run without a database, browser download, or live scraping:
    python -m unittest tests.test_dependency_security
"""

import hashlib
import io
import re
import ssl
import unittest
from unittest.mock import Mock, patch

import certifi
import requests
from curl_cffi.requests import Session as CurlSession
from dotenv import dotenv_values
from playwright.sync_api import sync_playwright
from urllib3.util.ssl_ import create_urllib3_context


class TestDependencySecurity(unittest.TestCase):
    def test_certifi_excludes_removed_emsign_roots(self):
        """Inspect the shipped bundle, independently of any host trust store."""
        certificates = re.findall(
            r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
            certifi.contents(),
            flags=re.DOTALL,
        )
        self.assertTrue(certificates)
        fingerprints = {
            hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()
            for pem in certificates
        }
        # G3, C1 and C3: upstream removals in certifi 2026.10.18/2026.10.23.
        # https://github.com/certifi/python-certifi/pull/437
        # https://github.com/certifi/python-certifi/pull/445
        removed_roots = {
            "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b",
            "125609aa301da0a249b97a8239cb6a34216f44dcac9f3954b14292f2e8c8608f",
            "bc4d809b15189d78db3e1d8cf4f9726a795da1643ca5f1358e1ddb0edc0d7eb3",
        }
        self.assertTrue(removed_roots.isdisjoint(fingerprints))

    def test_requests_keeps_tls_verification_and_idna_support(self):
        with requests.Session() as session:
            self.assertTrue(session.verify)
            self.assertEqual(requests.certs.where(), certifi.where())
            prepared = requests.Request("GET", "https://bücher.example/").prepare()
            self.assertEqual(prepared.url, "https://xn--bcher-kva.example/")

    def test_urllib3_requires_verified_certificates(self):
        context = create_urllib3_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_http_helper_uses_requests_without_disabling_verification(self):
        from src.utils.http import make_request

        response = Mock(text="<html>offline fixture</html>")
        with patch("src.utils.http.requests.get", return_value=response) as get:
            self.assertEqual(make_request("https://example.com/"), response.text)
        get.assert_called_once_with(
            "https://example.com/", headers={}, proxies=None, timeout=20
        )
        response.raise_for_status.assert_called_once_with()

    def test_dotenv_parsing_remains_compatible(self):
        values = dotenv_values(stream=io.StringIO('LABEL="two words"\nCOUNT=2\n'))
        self.assertEqual(values, {"LABEL": "two words", "COUNT": "2"})

    def test_curl_session_initializes_without_network(self):
        with CurlSession(impersonate="chrome110") as session:
            self.assertTrue(session.verify)

    def test_playwright_driver_starts_without_launching_a_browser(self):
        with sync_playwright() as playwright:
            self.assertEqual(playwright.chromium.name, "chromium")


if __name__ == "__main__":
    unittest.main()
