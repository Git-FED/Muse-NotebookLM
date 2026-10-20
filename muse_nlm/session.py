"""One-time session storage for authenticated NotebookLM fetches.

The tool ships with no browser and no third-party libraries, so the session is
a cookie header exported by hand from a signed-in browser (see README.md). This
module is the single home for where that value lives and how it is reported;
``cli.py`` only formats what this module returns.

The session file contains Google session cookies in plain text, so the config
directory is created ``0o700`` and the file is written ``0o600``.
"""

from __future__ import annotations

import json
import os
import pathlib
from typing import Any, Dict, Optional

CONFIG_DIR = (
    pathlib.Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    / "muse-nlm"
)
SESSION_PATH = CONFIG_DIR / "session.json"


def load() -> Optional[Dict[str, Any]]:
    """Return the stored session dict, or ``None`` if there is no usable one."""
    try:
        raw = SESSION_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict) or not data.get("cookie"):
        return None
    return data


def save(cookie: str, email: Optional[str] = None) -> pathlib.Path:
    """Persist a session and return the path it was written to."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)

    payload: Dict[str, Any] = {"cookie": cookie}
    if email:
        payload["email"] = email

    SESSION_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.chmod(SESSION_PATH, 0o600)
    return SESSION_PATH


def clear() -> bool:
    """Delete the stored session. Return ``True`` if a file was removed."""
    try:
        SESSION_PATH.unlink()
        return True
    except FileNotFoundError:
        return False


def status() -> str:
    """Return a human-readable one-line summary of the current login state."""
    session = load()
    if not session:
        return "not logged in"
    who = session.get("email") or "unknown account"
    return f"logged in as {who} (session: {SESSION_PATH})"
