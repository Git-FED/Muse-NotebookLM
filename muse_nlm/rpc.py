"""Client for NotebookLM's ``batchexecute`` RPC endpoint.

NotebookLM's web app loads all notebook content through one endpoint:

    POST {base}/_/LabsTailwindUi/data/batchexecute

The wire format here follows the one used by the open-source notebooklm-py
client (verified against its source 2026-10-20):

- Query params: ``rpcids``, ``source-path``, ``f.sid`` (the page's
  ``FdrFJe`` value), ``hl``, ``rt=c``. Nothing else.
- Body: ``f.req=<urlencoded triple-nested envelope>`` plus ``at=<the
  page's SNlM0e CSRF token>`` and a trailing ``&``.
- Response: an XSSI prefix, then alternating byte-count lines and JSON
  chunks. Result frames are tagged ``wrb.fr``; when several frames carry
  the same rpc id, the LAST non-null result wins. A null result with a
  status array at frame index 5 is a rejection (gRPC canonical codes:
  3 = invalid/quota, 5 = not found, 8 = rate limit).

This module owns the wire format and the single POST. It knows nothing
about notebooks; see :mod:`muse_nlm.notebooks` for the read operations.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Sequence

from . import fetch as _fetch

BASE_URL = "https://notebook.google.com"
BATCHEXECUTE_PATH = "/_/LabsTailwindUi/data/batchexecute"

XSSI_PREFIX = ")]}'"

# gRPC canonical status codes seen in rejection envelopes.
STATUS_NAMES = {
    3: "INVALID_ARGUMENT (or quota exhausted)",
    5: "NOT_FOUND",
    8: "RESOURCE_EXHAUSTED (rate limit / quota)",
    13: "INTERNAL",
}


class RpcError(Exception):
    """Raised when an RPC call fails, is rejected, or returns no result."""


class RpcNotFound(RpcError):
    """Raised when the server reports the target does not exist (code 5)."""


def build_f_req(rpc_id: str, args: Sequence[Any]) -> str:
    """Encode one RPC call as the ``f.req`` form field value.

    Wire shape: ``[[["<rpc_id>","<args as JSON string>",null,"generic"]]]``
    """
    args_json = json.dumps(list(args), separators=(",", ":"), ensure_ascii=False)
    envelope = [[[rpc_id, args_json, None, "generic"]]]
    return json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)


def build_body(rpc_id: str, args: Sequence[Any], csrf_token: str) -> bytes:
    """Build the full urlencoded POST body for one RPC call."""
    body = "f.req=" + urllib.parse.quote(build_f_req(rpc_id, args), safe="")
    if csrf_token:
        body += "&at=" + urllib.parse.quote(csrf_token, safe="")
    body += "&"
    return body.encode("utf-8")


def build_url(
    rpc_id: str, session_id: str, source_path: str = "/", language: str = "en"
) -> str:
    """Build the batchexecute URL for one RPC call."""
    params = {
        "rpcids": rpc_id,
        "source-path": source_path,
        "f.sid": session_id,
        "hl": language,
        "rt": "c",
    }
    return BASE_URL + BATCHEXECUTE_PATH + "?" + urllib.parse.urlencode(params)


def _iter_frames(text: str):
    """Yield every frame (list entry) from a batchexecute response body."""
    body = text
    if body.startswith(XSSI_PREFIX):
        body = body[len(XSSI_PREFIX) :]
    decoder = json.JSONDecoder()
    idx = 0
    length = len(body)
    while idx < length:
        while idx < length and body[idx] in " \t\r\n":
            idx += 1
        if idx >= length:
            break
        if body[idx].isdigit():
            newline = body.find("\n", idx)
            if newline < 0:
                break
            idx = newline + 1
            continue
        if body[idx] != "[":
            break
        try:
            chunk, end = decoder.raw_decode(body, idx)
        except json.JSONDecodeError:
            break
        idx = end
        if isinstance(chunk, list):
            for entry in chunk:
                if isinstance(entry, list):
                    yield entry


def parse_response(text: str, rpc_id: str) -> Any:
    """Return the decoded result payload for ``rpc_id`` from a response.

    Raises :class:`RpcNotFound` on a NOT_FOUND rejection, :class:`RpcError`
    on other rejections, error frames, or when no frame carries the id.
    """
    result: Any = None
    found = False
    for frame in _iter_frames(text):
        if len(frame) < 3:
            continue
        if frame[0] == "er" and frame[1] == rpc_id:
            raise RpcError(f"RPC {rpc_id} error frame: {frame[2]!r}")
        if frame[0] != "wrb.fr" or frame[1] != rpc_id:
            continue
        raw = frame[2]
        if raw is None:
            status = frame[5] if len(frame) > 5 else None
            if isinstance(status, list) and status and isinstance(status[0], int):
                code = status[0]
                name = STATUS_NAMES.get(code, f"status {code}")
                if code == 5:
                    raise RpcNotFound(f"RPC {rpc_id} rejected: {name}")
                raise RpcError(f"RPC {rpc_id} rejected: {name}")
            continue  # null placeholder; a later frame may carry the result
        if isinstance(raw, str):
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                result = raw
        else:
            result = raw
        found = True
    if not found:
        raise RpcError(
            f"RPC {rpc_id} returned no result frame "
            "(method id may have changed, or the response was not an RPC stream)"
        )
    return result


def call(
    rpc_id: str,
    args: Sequence[Any],
    *,
    cookie: str,
    csrf_token: str,
    session_id: str,
    source_path: str = "/",
    language: str = "en",
    timeout: float = _fetch.DEFAULT_TIMEOUT,
) -> Any:
    """Run one RPC and return its decoded result payload."""
    url = build_url(rpc_id, session_id, source_path=source_path, language=language)
    headers = {
        "User-Agent": _fetch.USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Cookie": cookie,
    }
    request = urllib.request.Request(
        url, data=build_body(rpc_id, args, csrf_token), headers=headers
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
    except socket.timeout as exc:
        raise RpcError(f"RPC {rpc_id} timed out after {timeout:g}s") from exc
    except urllib.error.HTTPError as exc:
        raise RpcError(f"RPC {rpc_id} got HTTP {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RpcError(f"RPC {rpc_id} could not reach endpoint: {exc.reason}") from exc
    except OSError as exc:
        raise RpcError(f"RPC {rpc_id} network error: {exc}") from exc
    return parse_response(text, rpc_id)


def parse_notebook_id(url: str) -> Optional[str]:
    """Return the notebook id from a ``/notebook/<id>`` URL, or ``None``."""
    parts = [p for p in urllib.parse.urlparse(url).path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "notebook":
        return parts[1]
    return None
