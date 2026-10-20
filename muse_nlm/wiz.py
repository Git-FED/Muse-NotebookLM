"""Extract the ``WIZ_global_data`` bootstrap tokens from a NotebookLM page.

NotebookLM is a Google "Wiz" app: the initial HTML embeds a JSON blob named
``WIZ_global_data`` holding the values the web client needs to talk to the
``batchexecute`` RPC endpoint — most importantly the CSRF token and the
session id. A static fetch can read them straight out of the page; no
JavaScript execution is required.

This module only parses. It never touches the network.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

_MARKER = "WIZ_global_data"


class WizError(Exception):
    """Raised when the bootstrap blob is missing or unparsable."""


def _extract_object(html: str) -> str:
    """Return the raw ``{...}`` text assigned to ``WIZ_global_data``."""
    idx = html.find(_MARKER)
    if idx < 0:
        raise WizError("WIZ_global_data not found in page")
    brace = html.find("{", idx)
    if brace < 0:
        raise WizError("WIZ_global_data has no object literal")

    depth = 0
    in_str = False
    escape = False
    for pos in range(brace, len(html)):
        ch = html[pos]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return html[brace : pos + 1]
    raise WizError("WIZ_global_data object is not terminated")


def load_wiz_data(html: str) -> Dict[str, Any]:
    """Parse and return the ``WIZ_global_data`` dict from page HTML."""
    raw = _extract_object(html)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WizError(f"WIZ_global_data is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise WizError("WIZ_global_data is not an object")
    return data


def get_token(html: str, key: str) -> Optional[str]:
    """Return one string token from the bootstrap blob, or ``None``."""
    try:
        data = load_wiz_data(html)
    except WizError:
        return None
    value = data.get(key)
    return value if isinstance(value, str) and value else None


# Well-known keys (per the notebooklm-py source, verified 2026-10-20):
#   SNlM0e -> the "at" CSRF token sent in batchexecute POST bodies
#   FdrFJe -> the session id sent as the "f.sid" query parameter
CSRF_KEY = "SNlM0e"
SESSION_ID_KEY = "FdrFJe"


def csrf_token(html: str) -> Optional[str]:
    return get_token(html, CSRF_KEY)


def session_id(html: str) -> Optional[str]:
    return get_token(html, SESSION_ID_KEY)
