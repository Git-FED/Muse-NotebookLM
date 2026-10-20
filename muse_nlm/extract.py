"""Convert NotebookLM HTML into clean plain text, standard library only.

This is a pure function of its input: it never touches the network, which is
what makes it cheap to test against saved fixtures. It deliberately keys off
semantics (skip non-visible tags, break on block elements) rather than
NotebookLM's class names, which change without notice.

When the input is an app shell (no real content), the result is empty rather
than a wall of navigation chrome, so the CLI can distinguish "empty" from
"worked" and exit accordingly.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import List

# Tags whose text content should never appear in the output.
_SKIP_TAGS = {
    "script",
    "style",
    "noscript",
    "template",
    "head",
    "svg",
    "iframe",
}

# Tags that imply a line break in the output.
_BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "dd",
    "div",
    "dl",
    "dt",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}


class _TextExtractor(HTMLParser):
    """Collect visible text, collapsing block boundaries into newlines."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_startendtag(self, tag: str, attrs) -> None:
        # Self-closing tags such as <br/>.
        if tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._parts.append(data)

    def text(self) -> str:
        raw = "".join(self._parts)
        lines = (line.strip() for line in raw.splitlines())
        return "\n".join(line for line in lines if line)


def html_to_text(html: str) -> str:
    """Return the readable text of ``html`` with whitespace collapsed.

    Returns an empty string when the page contains no visible content (for
    example a JavaScript-only app shell).
    """
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.text()
