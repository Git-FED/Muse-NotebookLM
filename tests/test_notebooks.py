from muse_nlm import notebooks as nb

# Spec-shaped rows (notebooklm-py layouts, verified 2026-10-20).


def _source_row():
    meta = [None] * 20
    meta[1] = 1234  # word count
    meta[4] = 3  # type code: PDF
    return [["src-1"], "Quarterly Report.pdf", meta, [None, 2]]


def _project_row(with_sources=False):
    row = [None] * 12
    row[0] = "thought\nResearch Notebook"  # decoder strips the prefix quirk
    row[1] = [_source_row()] if with_sources else [_source_row()]
    row[2] = "nb-42"
    row[3] = "\U0001f4d3"
    return row


def test_decode_notebook_strips_thought_prefix():
    out = nb.decode_notebook(_project_row())
    assert out["id"] == "nb-42"
    assert out["title"] == "Research Notebook"
    assert out["source_count"] == 1


def test_decode_source_pdf():
    out = nb.decode_source(_source_row())
    assert out["id"] == "src-1"
    assert out["title"] == "Quarterly Report.pdf"
    assert out["type"] == "PDF"
    assert out["word_count"] == 1234


def test_decode_source_drive_envelope():
    row = [[None, True, ["drive-id-9"]], "Doc", [None] * 20, None]
    assert nb.decode_source(row)["id"] == "drive-id-9"


def test_decode_notebook_with_sources():
    out = nb.decode_notebook(_project_row(), with_sources=True)
    assert out["sources"][0]["id"] == "src-1"


def test_extract_all_text_tree():
    tree = ["Hello", ["nested", ["deep", "world"]], 42, None]
    text = nb.extract_all_text(tree)
    assert text.split("\n") == ["Hello", "nested", "deep", "world"]


def test_client_requires_cookie():
    try:
        nb.NotebookClient("")
        assert False, "expected NotebookError"
    except nb.NotebookError:
        pass
