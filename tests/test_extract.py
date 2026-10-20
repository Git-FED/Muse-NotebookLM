"""Offline tests for the HTML -> text extractor."""

from muse_nlm import extract


def test_extracts_visible_text(read_fixture):
    text = extract.html_to_text(read_fixture("notebook.html"))
    assert "Photosynthesis" in text
    assert "chlorophyll" in text
    assert "Calvin cycle" in text


def test_shell_yields_no_content(read_fixture):
    # The logged-out app shell must produce nothing readable, so the CLI can
    # report "no content" instead of printing chrome.
    text = extract.html_to_text(read_fixture("shell.html"))
    assert len(text) < 40


def test_skips_script_and_style():
    html = (
        "<html><head><style>.a{color:red}</style></head>"
        "<body><script>var x = 1;</script><p>Hello</p></body></html>"
    )
    assert extract.html_to_text(html) == "Hello"


def test_collapses_whitespace_and_blank_lines():
    html = "<div><p>  a  </p>\n\n\n<p>b</p></div>"
    assert extract.html_to_text(html) == "a\nb"


def test_empty_input_is_empty():
    assert extract.html_to_text("") == ""
