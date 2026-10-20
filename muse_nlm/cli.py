"""Command-line interface for muse-nlm.

The CLI is deliberately thin: it parses arguments, calls into the library
layers (session, fetch, extract), and owns the process exit code. All of the
interesting behaviour lives in those modules so it can be tested without a
terminal.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from typing import List, Optional

from . import __version__, extract, fetch, session

# Below this many characters of extracted text we assume the page was an app
# shell (or a login wall) rather than real notebook content.
MIN_CONTENT_CHARS = 40


def _cmd_open(args: argparse.Namespace) -> int:
    if args.file:
        try:
            html = pathlib.Path(args.file).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"nlm: cannot read {args.file}: {exc}", file=sys.stderr)
            return 1
    elif args.url:
        try:
            html = fetch.fetch(
                args.url, timeout=args.timeout, session=session.load()
            )
        except fetch.FetchError as exc:
            print(f"nlm: {exc}", file=sys.stderr)
            return 1
    else:
        print("nlm: open needs a URL or --file", file=sys.stderr)
        return 2

    text = extract.html_to_text(html)
    if len(text) < MIN_CONTENT_CHARS:
        print(
            "nlm: no readable content found — the notebook may require a "
            "session (run `nlm login`).",
            file=sys.stderr,
        )
        return 3

    print(text)
    return 0


def _cmd_login(args: argparse.Namespace) -> int:
    cookie = args.cookie
    if not cookie:
        print(
            "Paste the Cookie header from your browser's devtools\n"
            "(NotebookLM tab -> Network -> any request -> Request Headers -> Cookie)."
        )
        try:
            cookie = input("Cookie: ").strip()
        except EOFError:
            cookie = ""

    if not cookie:
        print("nlm: no cookie provided", file=sys.stderr)
        return 1

    path = session.save(cookie, email=args.email)
    print(f"Saved session to {path} (chmod 600).")
    return 0


def _cmd_logout(args: argparse.Namespace) -> int:
    if session.clear():
        print("Session cleared.")
    else:
        print("No session to clear.")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    print(session.status())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nlm",
        description="Fetch NotebookLM links and print readable content as plain text.",
    )
    parser.add_argument(
        "--version", action="version", version=f"muse-nlm {__version__}"
    )
    sub = parser.add_subparsers(dest="command")

    p_open = sub.add_parser("open", help="fetch a URL and print readable text")
    p_open.add_argument("url", nargs="?", help="NotebookLM URL")
    p_open.add_argument(
        "--file", help="read HTML from a local file instead of the network"
    )
    p_open.add_argument(
        "--timeout",
        type=float,
        default=fetch.DEFAULT_TIMEOUT,
        help=f"request timeout in seconds (default: {fetch.DEFAULT_TIMEOUT:g})",
    )
    p_open.set_defaults(func=_cmd_open)

    p_login = sub.add_parser("login", help="store a session cookie")
    p_login.add_argument("--cookie", help="cookie header value (prompted if omitted)")
    p_login.add_argument("--email", help="optional account label for `nlm status`")
    p_login.set_defaults(func=_cmd_login)

    p_logout = sub.add_parser("logout", help="delete the stored session")
    p_logout.set_defaults(func=_cmd_logout)

    p_status = sub.add_parser("status", help="show login status")
    p_status.set_defaults(func=_cmd_status)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)
