"""HTTP fetching for muse-nlm, using only the standard library.

Two things matter here and are easy to get wrong:

1. ``urllib.request.urlopen`` has **no default timeout**. Without an explicit
   ``timeout=`` a stalled connection hangs forever. Every call in this module
   passes one.
2. A 403, a DNS failure, and a timeout mean very different things. They are
   raised as distinct, human-readable :class:`FetchError` messages so the CLI
   can report the real cause instead of a generic "it failed".
"""

from __future__ import annotations

import socket
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

DEFAULT_TIMEOUT = 15.0

# A default urllib User-Agent ("Python-urllib/3.x") is frequently served a bare
# shell or blocked outright, so identify honestly.
USER_AGENT = "muse-nlm/0.1 (+https://github.com/muse-nlm/muse-nlm)"


class FetchError(Exception):
    """Raised when a fetch fails in a way the CLI should report cleanly."""


def fetch(
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
    session: Optional[Dict[str, Any]] = None,
) -> str:
    """Fetch ``url`` and return the decoded response body as text.

    Raises :class:`FetchError` on timeout, HTTP error, or connection failure.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if session and session.get("cookie"):
        headers["Cookie"] = session["cookie"]

    request = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = None
            headers = getattr(response, "headers", None)
            if headers is not None and hasattr(headers, "get_content_charset"):
                charset = headers.get_content_charset()
            return response.read().decode(charset or "utf-8", errors="replace")
    except socket.timeout as exc:
        raise FetchError(f"timed out after {timeout:g}s fetching {url}") from exc
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP {exc.code} {exc.reason} fetching {url}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise FetchError(f"could not reach {url}: {reason}") from exc
    except OSError as exc:  # socket.error and friends
        raise FetchError(f"network error fetching {url}: {exc}") from exc
