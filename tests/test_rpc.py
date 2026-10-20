import json

from muse_nlm import rpc, wiz

PAGE = '<html><script>WIZ_global_data = {"SNlM0e":"csrf-abc","FdrFJe":"1234567890","other":"x"};</script></html>'


def _stream(*frames):
    chunk = json.dumps(list(frames))
    return ")]}'\n\n" + str(len(chunk)) + "\n" + chunk + "\n"


def _raises(exc_type, fn):
    try:
        fn()
    except exc_type:
        return True
    return False


def test_wiz_tokens():
    assert wiz.csrf_token(PAGE) == "csrf-abc"
    assert wiz.session_id(PAGE) == "1234567890"
    assert wiz.csrf_token("<html>no blob</html>") is None


def test_build_f_req_shape():
    body = json.loads(rpc.build_f_req("wXbhsf", [None, 1]))
    assert body[0][0][0] == "wXbhsf"
    assert json.loads(body[0][0][1]) == [None, 1]
    assert body[0][0][3] == "generic"


def test_build_url_params():
    url = rpc.build_url("wXbhsf", "999", source_path="/")
    assert "rpcids=wXbhsf" in url
    assert "f.sid=999" in url
    assert "rt=c" in url
    assert "soc-app" not in url and "_reqid" not in url and "bl=" not in url


def test_parse_response_basic():
    payload = json.dumps([[["nb-1", "My Notebook"]]])
    text = _stream(["wrb.fr", "wXbhsf", payload, None, None, None, "generic"])
    assert rpc.parse_response(text, "wXbhsf") == [[["nb-1", "My Notebook"]]]


def test_parse_response_last_non_null_wins():
    text = _stream(
        ["wrb.fr", "hizoJc", None, None, None, None, "generic"],
        ["wrb.fr", "hizoJc", json.dumps(["real"]), None, None, None, "generic"],
    )
    assert rpc.parse_response(text, "hizoJc") == ["real"]


def test_parse_response_not_found():
    text = _stream(["wrb.fr", "rLM1Ne", None, None, None, [5], "generic"])
    assert _raises(rpc.RpcNotFound, lambda: rpc.parse_response(text, "rLM1Ne"))


def test_parse_response_missing_id():
    text = _stream(["wrb.fr", "other", json.dumps(1), None, None, None, "generic"])
    assert _raises(rpc.RpcError, lambda: rpc.parse_response(text, "wXbhsf"))


def test_parse_notebook_id():
    assert (
        rpc.parse_notebook_id("https://notebooklm.google.com/notebook/abc-123")
        == "abc-123"
    )
    assert rpc.parse_notebook_id("https://notebooklm.google.com/") is None
