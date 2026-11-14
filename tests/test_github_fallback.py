"""When GitHub's API limit is used up, releases come from the public release page, checksums included."""
from types import SimpleNamespace

from cornerplay import net

PAGE = '''<a href="/o/r/releases/download/1.2/tool.deb" rel="nofollow">tool.deb</a>
<span>sha256:aaaa{0}</span><clipboard-copy value="sha256:aaaa{0}"></clipboard-copy>
<a href="/o/r/releases/download/1.2/tool-zipapp.tar" rel="nofollow">tool-zipapp.tar</a>
<span>sha256:bbbb{0}</span>
<a href="/o/r/archive/refs/tags/1.2.tar.gz">Source code</a>'''.format("0" * 60)


def test_falls_back_to_release_page(monkeypatch):
    def get(url, **kw):
        if "api.github.com" in url:
            return SimpleNamespace(status_code=403, url=url)
        if url.endswith("/releases/latest"):
            return SimpleNamespace(status_code=200, url="https://github.com/o/r/releases/tag/1.2", raise_for_status=lambda: None)
        assert url.endswith("/expanded_assets/1.2")
        return SimpleNamespace(status_code=200, url=url, text=PAGE, raise_for_status=lambda: None)
    monkeypatch.setattr(net, "requests", SimpleNamespace(get=get, ConnectionError=ConnectionError))
    tag, url, sha = net.github_asset("o/r", lambda n: n.endswith("-zipapp.tar"))
    assert (tag, url) == ("1.2", "https://github.com/o/r/releases/download/1.2/tool-zipapp.tar")
    assert sha == "bbbb" + "0" * 60
    rel = net.latest_release("o/r")
    assert [a["name"] for a in rel["assets"]] == ["tool.deb", "tool-zipapp.tar"]
