"""PhysX for games added by hand (redist.py) and Ubuntu's user-namespace block (userns.py)."""
import os
import subprocess

from cornerplay import redist, userns


def _exe(tmp_path, body=b"MZ\0\0kernel32.dll\0PHYSXLOADER.dll\0"):
    d = tmp_path / "Mafia II" / "pc"
    d.mkdir(parents=True)
    p = d / "mafia2.exe"
    p.write_bytes(body)
    return str(p)


def test_physx_needed_until_the_prefix_has_it(tmp_path):
    exe, prefix = _exe(tmp_path), tmp_path / "pfx"
    assert redist.needs_physx(exe, str(prefix))
    (prefix / "drive_c" / "windows" / "syswow64").mkdir(parents=True)
    (prefix / "drive_c" / "windows" / "syswow64" / "PhysXLoader.dll").write_bytes(b"x")
    assert not redist.needs_physx(exe, str(prefix))


def test_physx_not_needed(tmp_path):
    prefix = str(tmp_path / "pfx")
    assert not redist.needs_physx(_exe(tmp_path, b"MZ\0\0kernel32.dll\0"), prefix)  # does not ask for it
    exe = str(tmp_path / "Mafia II" / "pc" / "mafia2.exe")
    open(exe, "wb").write(b"MZ PhysXLoader.dll")
    open(os.path.join(os.path.dirname(exe), "physxloader.dll"), "wb").write(b"x")  # brought its own
    assert not redist.needs_physx(exe, prefix)


def test_physx_name_across_read_chunks(tmp_path):
    body = b"MZ" + b"\0" * ((1 << 20) - 8) + b"PhysXLoader.dll"  # straddles the 1 MB boundary
    assert redist.needs_physx(_exe(tmp_path, body), str(tmp_path / "pfx"))


def test_wrap_installs_once_then_starts_the_game(tmp_path, monkeypatch):
    exe, prefix = _exe(tmp_path), tmp_path / "pfx"
    prefix.mkdir()
    log = tmp_path / "log"
    tool = tmp_path / "umu-run"  # stands in for umu-run: records its arguments
    tool.write_text(f'#!/bin/sh\necho "umu $*" >> {log}\n')
    tool.chmod(0o755)
    monkeypatch.setattr("cornerplay.runner.compat", lambda: ("umu", str(tool)))
    argv = redist.wrap([str(tool), exe, "-dx9"], exe, str(prefix))
    assert subprocess.run(argv).returncode == 0
    assert log.read_text().splitlines() == ["umu winetricks -q physx", f"umu {exe} -dx9"]
    assert redist.wrap([str(tool), exe], exe, str(prefix)) == [str(tool), exe]  # tried once: never again


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
