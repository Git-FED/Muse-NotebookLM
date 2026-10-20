"""Notebook read operations on top of :mod:`muse_nlm.rpc`.

Implements the three reads a Muse agent needs:

- ``list_notebooks`` — rpcid ``wXbhsf`` (most recently viewed first)
- ``get_notebook``   — rpcid ``rLM1Ne`` (notebook + its source list)
- ``get_source_text`` / ``get_source_html`` — rpcid ``hizoJc`` (full text)

Row layouts follow the notebooklm-py source (verified 2026-10-20). A
Project row is ``[title, sources, id, emoji, ...]`` with metadata at index
5. A Source row is ``[id-envelope, title, metadata, settings, ...]`` with
the source type code at ``metadata[4]``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import fetch, rpc, wiz

# Sent as a params slot in most notebook/source RPCs.
TEMPLATE_BLOCK = [
    2,
    None,
    None,
    [1, None, None, None, None, None, None, None, None, None, [1]],
]

SOURCE_TYPE_NAMES = {
    1: "Google Doc",
    2: "Google Slides",
    3: "PDF",
    4: "Pasted text",
    5: "Web page",
    6: "PowerPoint",
    7: "Google Sheet",
    8: "Markdown",
    9: "YouTube",
    10: "Media",
    11: "DOCX",
    12: "Excel",
    13: "Image",
    14: "Google Drive",
    15: "Gmail",
    16: "CSV",
    17: "EPUB",
    18: "Gemini chat",
    19: "AI Mode chat",
    20: "Expert intelligence",
}


class NotebookError(Exception):
    """Raised when a notebook operation cannot be completed."""


def _at(seq: Any, index: int, default: Any = None) -> Any:
    if isinstance(seq, list) and 0 <= index < len(seq):
        return seq[index]
    return default


def decode_source_id(envelope: Any) -> Optional[str]:
    """Pull the source id out of its envelope (three shapes in the wild)."""
    if isinstance(envelope, str):
        return envelope
    if isinstance(envelope, list) and envelope:
        first = envelope[0]
        if isinstance(first, str):
            return first
        # Drive-backed form: [None, True, ["<id>"]]
        third = _at(envelope, 2)
        if isinstance(third, list) and third and isinstance(third[0], str):
            return third[0]
    return None


def decode_source(row: Any) -> Dict[str, Any]:
    """Decode one Source row into a plain dict."""
    meta = _at(row, 2) or []
    type_code = _at(meta, 4)
    url = None
    canonical = _at(meta, 7)
    if isinstance(canonical, list) and canonical and isinstance(canonical[0], str):
        url = canonical[0]
    if url is None:
        youtube = _at(meta, 5)
        if isinstance(youtube, list) and youtube and isinstance(youtube[0], str):
            url = youtube[0]
    return {
        "id": decode_source_id(_at(row, 0)),
        "title": _at(row, 1),
        "type_code": type_code,
        "type": SOURCE_TYPE_NAMES.get(type_code, "Unknown"),
        "word_count": _at(meta, 1),
        "url": url,
    }


def decode_notebook(row: Any, *, with_sources: bool = False) -> Dict[str, Any]:
    """Decode one Project row into a plain dict."""
    title = _at(row, 0)
    if isinstance(title, str) and title.startswith("thought\n"):
        title = title[len("thought\n") :]
    sources_raw = _at(row, 1) or []
    decoded: Dict[str, Any] = {
        "id": _at(row, 2),
        "title": title,
        "emoji": _at(row, 3),
        "source_count": len(sources_raw) if isinstance(sources_raw, list) else 0,
    }
    if with_sources:
        decoded["sources"] = [
            decode_source(s) for s in sources_raw if isinstance(s, list)
        ]
    return decoded


def extract_all_text(node: Any, _depth: int = 0) -> str:
    """Recursively collect every string in a fulltext tree, in order."""
    if _depth > 100:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        parts = [extract_all_text(child, _depth + 1) for child in node]
        return "\n".join(p for p in parts if p)
    if isinstance(node, dict):
        parts = [extract_all_text(v, _depth + 1) for v in node.values()]
        return "\n".join(p for p in parts if p)
    return ""


class NotebookClient:
    """A read-only NotebookLM client bound to one session cookie."""

    def __init__(self, cookie: str, timeout: float = fetch.DEFAULT_TIMEOUT):
        if not cookie:
            raise NotebookError("no session cookie — run `nlm login` first")
        self._cookie = cookie
        self._timeout = timeout
        self._csrf: Optional[str] = None
        self._sid: Optional[str] = None

    def _tokens(self) -> tuple:
        if self._csrf is None or self._sid is None:
            html = fetch.fetch(
                rpc.BASE_URL + "/",
                timeout=self._timeout,
                session={"cookie": self._cookie},
            )
            self._csrf = wiz.csrf_token(html)
            self._sid = wiz.session_id(html)
            if not self._csrf or not self._sid:
                raise NotebookError(
                    "could not read session tokens from the NotebookLM page "
                    "— the stored cookie is likely expired (run `nlm login` again)"
                )
        return self._csrf, self._sid

    def _call(self, rpc_id: str, args: list, source_path: str = "/") -> Any:
        csrf, sid = self._tokens()
        return rpc.call(
            rpc_id,
            args,
            cookie=self._cookie,
            csrf_token=csrf,
            session_id=sid,
            source_path=source_path,
            timeout=self._timeout,
        )

    def list_notebooks(self) -> List[Dict[str, Any]]:
        result = self._call("wXbhsf", [None, 1, None, [2]], source_path="/")
        rows = _at(result, 0) or []
        return [decode_notebook(r) for r in rows if isinstance(r, list)]

    def get_notebook(self, notebook_id: str) -> Dict[str, Any]:
        result = self._call(
            "rLM1Ne",
            [notebook_id, None, TEMPLATE_BLOCK, None, 0],
            source_path=f"/notebook/{notebook_id}",
        )
        row = _at(result, 0)
        if not isinstance(row, list):
            raise NotebookError(f"notebook {notebook_id} not found or empty")
        return decode_notebook(row, with_sources=True)

    def _fulltext(self, notebook_id: str, source_id: str, variant: int) -> Any:
        return self._call(
            "hizoJc",
            [[source_id], [variant], [variant]],
            source_path=f"/notebook/{notebook_id}",
        )

    def get_source_text(self, notebook_id: str, source_id: str) -> str:
        result = self._fulltext(notebook_id, source_id, 2)
        tree = _at(_at(result, 3), 0)
        if tree is None:
            raise NotebookError(f"source {source_id} has no readable text")
        return extract_all_text(tree)

    def get_source_html(self, notebook_id: str, source_id: str) -> str:
        result = self._fulltext(notebook_id, source_id, 3)
        html = _at(_at(result, 4), 1)
        if not isinstance(html, str):
            raise NotebookError(f"source {source_id} has no HTML rendition")
        return html
