"""Ubuntu's user-namespace block (userns.py)."""

from cornerplay import userns


def test_userns(tmp_path, monkeypatch):
    flag, prof = tmp_path / "flag", tmp_path / "cornerplay-umu"
    monkeypatch.setattr(userns, "SYSCTL", str(flag))
    monkeypatch.setattr(userns, "PROFILE", str(prof))
    assert not userns.restricted() and not userns.blocked()  # not Ubuntu
    flag.write_text("1\n")
    assert userns.blocked()
    prof.write_text(userns.PROFILE_TEXT)
    assert not userns.blocked()
    assert "userns," in userns.PROFILE_TEXT and "/.local/share/umu/" in userns.PROFILE_TEXT
    assert userns.manual_command().endswith("apparmor_parser -r " + str(prof))
