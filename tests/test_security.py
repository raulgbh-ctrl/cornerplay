"""The protections around files and data that come from outside."""
import json
import os
import stat
import zipfile

import pytest

from cornerplay import backup, details, net, personal, playtime
from cornerplay.config import CONFIG_DIR, settings, write_private


def test_redact_hides_keys_and_tokens():
    msg = ("403 Client Error: Forbidden for url: https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
           "?key=ABCDEF123&steamid=7656&format=json")
    out = net.redact(msg)
    assert "ABCDEF123" not in out and "steamid=7656" in out
    assert "tok123" not in net.redact("Authorization: Bearer tok123")
    assert "s3cr3t" not in net.redact("x?client_secret=s3cr3t&refresh_token=r1")


def test_private_files(tmp_path):
    f = tmp_path / "a.json"
    write_private(f, "{}")
    assert stat.S_IMODE(f.stat().st_mode) == 0o600


def test_settings_and_config_dir_are_private():
    settings.set("card_size", settings.get("card_size"))
    assert stat.S_IMODE((CONFIG_DIR / "settings.json").stat().st_mode) == 0o600
    assert stat.S_IMODE(CONFIG_DIR.stat().st_mode) == 0o700


def _evil_backup(path, names):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("cornerplay-backup.json", "{}")
        for n in names:
            z.writestr(n, "pwned")


@pytest.mark.parametrize("name", ["config//tmp/pwned-abs", "config/../../pwned-up", "data/people/../../../pwned",
                                  "config/sub/../../pwned2", "other/pwned"])
def test_restore_never_writes_outside(tmp_path, name):
    evil = tmp_path / "b.zip"
    _evil_backup(evil, [name])
    assert backup._target(name) is None
    backup.restore(evil)
    assert not os.path.exists("/tmp/pwned-abs")
    assert not (CONFIG_DIR.parent / "pwned-up").exists()


def test_backup_leaves_out_keys_and_restore_keeps_them(tmp_path):
    settings.set("steam_api_key", "MYKEY")
    settings.set("igdb_client_secret", "MYSECRET")
    path = backup.make(tmp_path)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    with zipfile.ZipFile(path) as z:
        saved = json.loads(z.read("config/settings.json"))
    assert "steam_api_key" not in saved and "igdb_client_secret" not in saved
    backup.restore(path)
    assert json.loads((CONFIG_DIR / "settings.json").read_text())["steam_api_key"] == "MYKEY"
    settings.data.update(steam_api_key="", igdb_client_secret="")


def test_store_text_cannot_smuggle_markup():
    out = details.clean('Fun &lt;img src="file:///etc/passwd"&gt; game <b>bold</b> &amp; more')
    assert "<" not in out and "img" not in out and "& more" in out


def test_malformed_sync_data_is_dropped():
    m = personal._merge({"games": [], "collections": "x", "deleted": 5},
                        {"games": {"a:1": {"t": "soon"}, "a:2": {"rating": 4, "t": 3}}, "collections": [1, "Co-op"]})
    assert m["games"] == {"a:2": {"rating": 4, "t": 3}} and m["collections"] == ["Co-op"]


def test_malformed_playtime_from_another_pc():
    own, _ = personal.playtime_files("playtime")
    own.parent.mkdir(parents=True, exist_ok=True)
    own.with_name("playtime-evil.json").write_text(json.dumps({"x:1": {"seconds": "lots"}, "x:2": 5, "x:3": {"seconds": 7}}))
    own.with_name("sessions-evil.json").write_text(json.dumps([["x:3", "a", 1], ["x:3", 1, 2], "junk"]))
    data = playtime.load()
    assert data["x:3"]["seconds"] == 7 and "x:1" not in data
    assert ["x:3", 1, 2] in playtime.sessions()


def test_update_downloads_only_from_this_project():
    from cornerplay import updates
    with pytest.raises(RuntimeError):
        updates.download("https://evil.example/cornerplay.run")
    with pytest.raises(RuntimeError):
        updates.download("https://github.com/someone-else/cornerplay/releases/download/v1/cornerplay.run")


def test_download_checked_rejects_mismatch(tmp_path, monkeypatch):
    class R:
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def raise_for_status(self): pass
        def iter_content(self, n): yield b"payload"
    monkeypatch.setattr(net.requests, "get", lambda *a, **k: R(), raising=False)
    with pytest.raises(RuntimeError):
        net.download_checked("https://x/y", tmp_path / "y", sha256="00" * 32)
    assert not (tmp_path / "y").exists() and not (tmp_path / "y.part").exists()
    import hashlib
    net.download_checked("https://x/y", tmp_path / "y", sha256=hashlib.sha256(b"payload").hexdigest(), mode=0o755)
    assert (tmp_path / "y").read_bytes() == b"payload"


def test_host_import_only_writes_inside_its_folders(tmp_path):
    import io
    import tarfile
    from cornerplay import hostimport
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as t:
        for name in ("cornerplay/settings.json", "./legendary/user.json", "../escape", "/etc/passwd",
                     "cornerplay/../../x", "other/file", "legendary/tmp/big", "cornerplay/bin/legendary"):
            info = tarfile.TarInfo(name)
            info.size = 1
            t.addfile(info, io.BytesIO(b"x"))
        link = tarfile.TarInfo("cornerplay/link")
        link.type, link.linkname = tarfile.SYMTYPE, "/home"
        t.addfile(link)
    buf.seek(0)
    with tarfile.open(fileobj=buf, mode="r|") as t:
        names = [m.name for m in hostimport._safe_members(t, {"cornerplay", "legendary"},
                                                         ("legendary/tmp", "cornerplay/bin"))]
    assert names == ["cornerplay/settings.json", "legendary/user.json"]


def test_flatpak_update_installs_with_the_hosts_flatpak(monkeypatch):
    from cornerplay import host, updates
    monkeypatch.setattr(host, "IN_FLATPAK", True)
    monkeypatch.setattr(updates, "_bundle", {"installation": "user"})
    cmd = updates.install_flatpak_argv("/home/u/.var/app/x/cache/cornerplay/cornerplay.flatpak")
    assert cmd[:2] == ["flatpak-spawn", "--host"] and "--bundle" in cmd and "--user" in cmd
    monkeypatch.setattr(updates, "_bundle", {})
    assert not updates.offered() or not updates.managed()


def test_backup_leaves_out_every_sign_in(tmp_path, monkeypatch):
    for name in ("humble_auth.json", "steam_web.json", "sunshine-login.json", "gog_auth.json", "new_store_auth.json"):
        write_private(CONFIG_DIR / name, "{}")
    try:
        names = {n for _, n in backup._files()}
        assert not any(n.endswith(("_auth.json", "steam_web.json", "sunshine-login.json")) for n in names)
    finally:
        for name in ("humble_auth.json", "steam_web.json", "sunshine-login.json", "gog_auth.json", "new_store_auth.json"):
            (CONFIG_DIR / name).unlink(missing_ok=True)


def test_family_pin_is_slow_hashed_and_locks_out(monkeypatch):
    from cornerplay import family
    family._tries.update(wrong=0, until=0, rounds=0)
    family.set_pin("1234")
    stored = settings.get("family_pin")
    assert stored.startswith("scrypt$") and "1234" not in stored
    assert family.pin_ok("1234")
    for _ in range(family.MAX_WRONG):
        assert not family.pin_ok("0000")
    assert family.pin_wait() > 0
    assert not family.pin_ok("1234")  # even the right PIN waits
    family._tries.update(wrong=0, until=0, rounds=0)
    assert family.pin_ok("1234")
    # an old salted SHA-256 PIN still works once and becomes scrypt
    import hashlib
    settings.set("family_pin", "ab$" + hashlib.sha256(b"ab9876").hexdigest())
    assert family.pin_ok("9876") and settings.get("family_pin").startswith("scrypt$")
    family.set_pin("")


def test_synced_settings_cannot_preload_code():
    from cornerplay import gamesync
    remote = {"steam:1": {"t": 5, "o": {"env": "LD_PRELOAD=/tmp/x.so DXVK_HUD=fps PATH=/tmp BASH_ENV=/tmp/rc",
                                       "args": ["--x"], "before": "rm -rf ~"}}}
    o = gamesync._clean(remote)["steam:1"]["o"]
    assert o == {"env": "DXVK_HUD=fps"}


def test_update_signature(tmp_path, monkeypatch):
    """Only a file signed with the project's key passes; another key, or a changed file, does not."""
    import shutil
    import subprocess
    from cornerplay import updates
    if not shutil.which("ssh-keygen"):
        pytest.skip("no ssh-keygen")
    keys = {}
    for name in ("ours", "theirs"):
        k = tmp_path / name
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(k)], check=True)
        keys[name] = k
    monkeypatch.setattr(updates, "PUBLIC_KEY", " ".join((tmp_path / "ours.pub").read_text().split()[:2]))
    f = tmp_path / "cornerplay.run"
    f.write_bytes(b"#!/bin/sh\necho hi\n")

    def sign(key):
        (tmp_path / "cornerplay.run.sig").unlink(missing_ok=True)
        subprocess.run(["ssh-keygen", "-Y", "sign", "-q", "-f", str(key), "-n", "cornerplay-release", str(f)], check=True)
        return tmp_path / "cornerplay.run.sig"

    assert updates.verify_signature(f, sign(keys["ours"]))
    assert not updates.verify_signature(f, sign(keys["theirs"]))
    sig = sign(keys["ours"])
    f.write_bytes(b"#!/bin/sh\nrm -rf ~\n")
    assert not updates.verify_signature(f, sig)


def test_signed_releases_need_their_signature(tmp_path, monkeypatch):
    from cornerplay import updates
    monkeypatch.setattr(updates, "CACHE_DIR", tmp_path)
    got = []

    def fake_download(url, dest, sha256="", mode=0o644, progress=None):
        got.append(url)
        dest.write_bytes(b"x")
        return str(dest)
    monkeypatch.setattr(updates, "download_checked", fake_download)
    monkeypatch.setattr(updates, "verify_signature", lambda p, s: False)
    url = updates.ASSET_PREFIX + "v0.19.1/cornerplay.run"
    with pytest.raises(RuntimeError, match="not signed"):
        updates.download(url, "", "0.19.1")
    assert got[-1] == url + ".sig" and not (tmp_path / "cornerplay.run").exists()
    updates.download(updates.ASSET_PREFIX + "v0.18.6/cornerplay.run", "", "0.18.6")  # before signing began


THROWAWAY_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFWDOXXIcgn2JfCwwED51UPYznw/BeSGjmICxc3fVu7X"
THROWAWAY_SIG = """-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgVYM5dchyCfYl8LDAQPnVQ9jOfD
8F5IaOYgLFzd9W7tcAAAASY29ybmVycGxheS1yZWxlYXNlAAAAAAAAAAZzaGE1MTIAAABT
AAAAC3NzaC1lZDI1NTE5AAAAQKDho7vQTLvEOFvsXTlL0cQRhqnnnPyzZL9fNu7XFC6+JM
Dc5T9b5PXUDGEj7Se6PVY5C3Q9nn5j3KncX/Do5wU=
-----END SSH SIGNATURE-----
"""


def test_signature_checked_without_ssh_keygen(tmp_path, monkeypatch):
    """Updates are checked in Python (sshsig.py), so Windows needs no OpenSSH: a signature made by
    `ssh-keygen -Y sign` with a throwaway key passes; another file, key or namespace does not."""
    from cornerplay import sshsig, updates
    f = tmp_path / "f"
    f.write_bytes(b"Cornerplay test file\n")
    sig = tmp_path / "f.sig"
    sig.write_text(THROWAWAY_SIG, newline="\r\n")  # Windows line ends are fine
    monkeypatch.setattr(updates, "PUBLIC_KEY", THROWAWAY_KEY)
    assert updates.verify_signature(f, sig)
    assert not sshsig.verify(THROWAWAY_KEY, "other-namespace", THROWAWAY_SIG, f)
    assert not sshsig.verify(updates.__dict__["PUBLIC_KEY"].replace("IFWD", "IFWE"), "cornerplay-release", THROWAWAY_SIG, f)
    f.write_bytes(b"Cornerplay test file!\n")
    assert not updates.verify_signature(f, sig)
