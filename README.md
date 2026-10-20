# muse-nlm

`nlm` fetches a NotebookLM link and prints the readable content as plain text.
No browser, no third-party packages — the standard library only.

```
nlm open https://notebooklm.google.com/notebook/<id>
```

## What it is

`muse-nlm` is a small, dependency-free command-line tool whose single job is to
turn a NotebookLM URL into readable text you can pipe somewhere else. It does
this with `urllib` for the network and `html.parser` for the parsing, so there is
nothing to install and nothing to keep patched. You can drop `bin/nlm` on a
machine that has only a Python 3.9+ interpreter and it will run.

The design is intentionally split into thin layers so each one can be tested in
isolation:

| Layer | Module | Responsibility |
|-------|--------|----------------|
| CLI | `muse_nlm/cli.py` | parse arguments, format output, own the exit code |
| Session | `muse_nlm/session.py` | store and report the one-time login state |
| Fetch | `muse_nlm/fetch.py` | perform the HTTP request with an explicit timeout |
| Wiz | `muse_nlm/wiz.py` | parse NotebookLM bootstrap tokens from HTML |
| RPC | `muse_nlm/rpc.py` | build batchexecute requests and parse RPC responses |
| Notebooks | `muse_nlm/notebooks.py` | list notebooks, decode sources, fetch source full text |
| Extract | `muse_nlm/extract.py` | convert HTML into clean plain text |

Nothing above the fetch layer touches the network, which is what makes the
extract and CLI layers testable offline.

## Install / run

There is nothing to install. Two entry points are supported:

```sh
# From anywhere, no install required (the shim fixes up sys.path itself):
./bin/nlm open <url>

# From the repository root only:
python -m muse_nlm open <url>
```

If you want `nlm` on your `PATH`, symlink the shim:

```sh
ln -s "$(pwd)/bin/nlm" ~/.local/bin/nlm
```

Make sure the shim is executable after a fresh checkout:

```sh
chmod +x bin/nlm
```

## Commands

### `nlm open <url>`

Fetches the URL and prints the readable content as plain text.

```sh
nlm open https://notebooklm.google.com/notebook/<id>
nlm open <url> --timeout 30          # override the 15s default
nlm open --file tests/fixtures/notebook.html   # parse a local file, no network
```

The `--file` form exists so you can parse a saved page (or a fixture) without
touching the network. It is also how the extractor is tested.

### `nlm list`

Lists your notebooks, most recently viewed first. Requires a stored session
(see `nlm login`).

```sh
$ nlm list
Research Notebook    nb-42    12 sources
Reading List         nb-77     3 sources
```

### `nlm notebook <id>`

Shows one notebook's title and every source in it, with each source's type
(PDF, web page, YouTube, pasted text, and more) and readiness status.

### `nlm source <notebook-id> <source-id>`

Prints one source's full text — the actual content of the PDF, page, or
document, extracted from the notebook's data — ready to pipe anywhere.

### `nlm login`

Stores the one-time session used for authenticated fetches. Because the tool
uses no browser and no third-party libraries, the session is a cookie you export
by hand from a browser where you are already signed in:

1. Open NotebookLM in your browser and sign in with your Google account.
2. Open developer tools → **Network**, reload, and click any request to
   `notebooklm.google.com`.
3. In **Request Headers**, copy the entire `Cookie:` value.
4. Run `nlm login` and paste it when prompted (or pass `--cookie "..."`).

```sh
nlm login                 # prompts for the cookie
nlm login --cookie "SID=...; HSID=..." --email you@gmail.com
```

### `nlm logout`

Deletes the stored session file.

### `nlm status`

Reports whether a session is stored, and where it lives.

```sh
$ nlm status
not logged in

$ nlm status
logged in as you@gmail.com (session: /home/you/.config/muse-nlm/session.json)
```

## Where the session lives

The session is stored at:

```
$XDG_CONFIG_HOME/muse-nlm/session.json      # default: ~/.config/muse-nlm/session.json
```

The directory is created `chmod 700` and the file is written `chmod 600`. The
file contains your Google session cookies in plain text, so treat it like a
password: it is git-ignored, and `nlm logout` removes it. If you are on a shared
machine, prefer running `nlm open` with an inline `--cookie` you paste each time
rather than persisting it.

## The honest limit

NotebookLM is a client-rendered single-page application. The notebook body is
**not** present in the initial HTML response — the app shell loads first, and
the actual content arrives afterwards through authenticated `batchexecute` RPC
calls made by the JavaScript.

This has two consequences you should understand before relying on the tool:

1. **Logged out**, `nlm open` will fetch the app shell and find no readable
   content. The CLI reports this explicitly and exits non-zero rather than
   printing navigation chrome and pretending it worked.
2. **Logged in**, a plain `GET` still returns the shell — the cookie alone is
   not sufficient for a static fetch to see the notes. That is why the read
   commands (`list`, `notebook`, `source`, and `open` on a notebook URL)
   replay the same `batchexecute` RPC calls the web app makes. As of v0.2.0
   that replay is built and tested: list notebooks (`wXbhsf`), notebook +
   sources (`rLM1Ne`), and source full text (`hizoJc`). Asking questions
   (chat) is not implemented yet.

In other words: no session, no notebook content — by design, not by bug.
The `--file` mode still lets you verify the extraction half against a page
you saved from a logged-in tab, independent of the session.

## Exit codes

`nlm open` distinguishes its failure modes so scripts and cron jobs can react:

| Code | Meaning |
|------|---------|
| 0 | success — readable content was printed |
| 1 | fetch or file error (timeout, HTTP error, unreadable file) |
| 2 | usage error (no URL and no `--file`) |
| 3 | the page loaded but contained no readable content (likely a login wall or app shell) |

The important one is **3**: an empty extraction is a failure, not a silent
success. A wrapper script can therefore tell "the notebook is empty" apart from
"the request worked."

## Development

Run the tests from the repository root:

```sh
python -m pytest
```

No install step is required. `pyproject.toml` sets `pythonpath = ["."]` under
`[tool.pytest.ini_options]`, which is the equivalent of an editable install for
import purposes only — nothing is added to site-packages.

The test suite is deliberately offline:

- `tests/test_extract.py` runs the parser against two fixtures:
  `shell.html` (the logged-out app shell, which should yield no content) and
  `notebook.html` (a saved page with real content).
- `tests/test_fetch.py` monkeypatches `urllib.request.urlopen` to exercise the
  timeout, HTTP-error, and connection-error branches without a network.
- `tests/test_rpc.py` locks in the batchexecute wire format: the request
  envelope, the session-token key, and response decoding (including the
  rejection envelope Google returns for bad or missing notebooks).
- `tests/test_notebooks.py` decodes captured-shape notebook and source rows:
  titles, source types, readiness status, and full-text extraction.

To add a new extractor case, drop an HTML file in `tests/fixtures/` and assert
against it. Because the extractor is pure, fixtures are the cheapest and most
reliable way to lock in behaviour.

## File layout

```text
Muse-NotebookLM
├── LICENSE
├── README.md
├── index.html                # public landing page with favicon and promo images
├── private-communities.html  # client-side age/residence self-check for Matrix invite
├── assets
│   ├── favicon.svg
│   ├── promo-library-chaos.png
│   └── promo-shell-goblin.png
├── manifest.json
├── pyproject.toml
├── bin
│   └── nlm
├── muse_nlm
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── extract.py
│   ├── fetch.py
│   ├── notebooks.py
│   ├── rpc.py
│   ├── session.py
│   └── wiz.py
└── tests
    ├── conftest.py
    ├── test_extract.py
    ├── test_fetch.py
    ├── test_notebooks.py
    ├── test_rpc.py
    └── fixtures
        ├── notebook.html
        └── shell.html
```
## License

MIT. See `LICENSE`.
