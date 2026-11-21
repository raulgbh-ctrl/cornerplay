"""Sunshine with address_family = both crashes at every stream start when there is no IPv6."""
from cornerplay import stream

CONF = "origin_web_ui_allowed = lan\naddress_family = both\nport = 47989\n"


def test_problem_only_without_ipv6():
    assert stream.conf_problem(CONF, ipv6=False) == "address_family"
    assert stream.conf_problem(CONF, ipv6=True) == ""
    assert stream.conf_problem("address_family = ipv4\n", ipv6=False) == ""
    assert stream.conf_problem("", ipv6=False) == ""


def test_has_ipv6(tmp_path):
    t = tmp_path / "if_inet6"
    t.write_text("00000000000000000000000000000001 01 80 10 80       lo\n"
                 "fe80000000000000021122fffe334455 02 40 20 80   wlan0\n")
    assert not stream.has_ipv6(str(t))  # loopback and link-local only
    t.write_text(t.read_text() + "2a02a58f000000000000000000000001 02 40 00 00   wlan0\n")
    assert stream.has_ipv6(str(t))
    assert not stream.has_ipv6(str(tmp_path / "missing"))


def test_fix_keeps_a_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(stream, "sunshine_dir", lambda: tmp_path)
    monkeypatch.setattr(stream, "has_ipv6", lambda: False)
    (tmp_path / "sunshine.conf").write_text(CONF)
    assert stream.fix_conf() is True
    assert "address_family" not in (tmp_path / "sunshine.conf").read_text()
    assert "port = 47989" in (tmp_path / "sunshine.conf").read_text()
    assert (tmp_path / "sunshine.conf.before-cornerplay").read_text() == CONF
    assert stream.fix_conf() is False  # nothing left to fix
