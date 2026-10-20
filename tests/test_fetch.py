"""Offline tests for the fetch layer, using a monkeypatched urlopen."""

import socket
import urllib.error
import urllib.request

import pytest

from muse_nlm import fetch


def test_timeout_surfaces_as_fetch_error(monkeypatch):
    def boom(*args, **kwargs):
        raise socket.timeout("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(fetch.FetchError) as exc:
        fetch.fetch("https://example.invalid", timeout=1)
    assert "timed out" in str(exc.value)


def test_http_error_surfaces_code(monkeypatch):
    def boom(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://example.invalid", 403, "Forbidden", {}, None
        )

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(fetch.FetchError) as exc:
        fetch.fetch("https://example.invalid")
    assert "403" in str(exc.value)


def test_connection_error_surfaces_reason(monkeypatch):
    def boom(*args, **kwargs):
        raise urllib.error.URLError("name or service not known")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(fetch.FetchError) as exc:
        fetch.fetch("https://example.invalid")
    assert "could not reach" in str(exc.value)


def test_session_cookie_is_sent(monkeypatch):
    captured = {}

    class FakeResponse:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"<html><body>ok</body></html>"

    def fake_urlopen(request, timeout=None):
        captured["cookie"] = request.get_header("Cookie")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    body = fetch.fetch(
        "https://example.invalid",
        timeout=7,
        session={"cookie": "SID=abc"},
    )
    assert "ok" in body
    assert captured["cookie"] == "SID=abc"
    assert captured["timeout"] == 7
