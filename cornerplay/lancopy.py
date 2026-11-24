"""Copy games from your other PCs over the home network, instead of downloading them again.

A PC that shares (Settings > People & sync > "Let my other PCs copy games from this one")
answers on port 47113: a UDP "who is there" for discovery, and HTTP for its list of installed
Epic, GOG and Amazon games and their files. Everything but discovery needs the PC's code
(shown under that setting; typed once on the other PC). Wrong codes are rate-limited.

The copying PC runs `python -m cornerplay.lancopy fetch ...` as an ordinary install job:
it prints progress and speed the way the store tools do (Downloads shows them), resumes
after a pause (files already complete are skipped, a partial one continues from where it
stopped), then runs the store's import command so the store knows the game is there.
"""
import json
import os
import secrets
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

PORT = 47113
HELLO = b"CORNERPLAY-WHO"
STORES = ("epic", "gog", "amazon")
MAX_FAILS = 5  # wrong codes per address per minute


def new_code() -> str:
    """Ten letters and digits people can read out (no 0/O, 1/I/L)."""
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(10))


def tidy_code(code: str) -> str:
    return "".join(c for c in (code or "").upper() if c.isalnum())


# --- the sharing PC -------------------------------------------------------------------------
def manifest(folder: str) -> list:
    """[[relative path, size, mode, symlink target or ""]] for everything in a game's folder."""
    out = []
    root = os.path.realpath(folder)
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files) + [d for d in dirs if os.path.islink(os.path.join(base, d))]:
            full = os.path.join(base, name)
            rel = os.path.relpath(full, root)
            try:
                st = os.lstat(full)
            except OSError:
                continue
            if os.path.islink(full):
                out.append([rel, 0, st.st_mode & 0o777, os.readlink(full)])
            elif os.path.isfile(full):
                out.append([rel, st.st_size, st.st_mode & 0o777, ""])
    return out


def inside(root: str, rel: str) -> str:
    """The file `rel` under `root`, or "" when it would leave the folder (../, links out)."""
    root = os.path.realpath(root)
    full = os.path.realpath(os.path.join(root, rel))
    return full if full.startswith(root + os.sep) and os.path.isfile(full) else ""


class Server:
    """games(): [{"key", "store", "id", "title", "path", "size"}] of what this PC has installed."""

    def __init__(self, name: str, code: str, games, port: int = PORT):
        self.name, self.code, self.games, self.port = name, tidy_code(code), games, port
        self._fails = {}
        self.http = self.udp = None

    def _ok(self, addr, given) -> bool:
        now = time.time()
        recent = [t for t in self._fails.get(addr, []) if now - t < 60]
        if len(recent) >= MAX_FAILS:
            return False
        if secrets.compare_digest(tidy_code(given), self.code):
            return True
        self._fails[addr] = recent + [now]
        return False

    def start(self):
        server = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _json(self, data, code=200):
                body = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if not server._ok(self.client_address[0], self.headers.get("X-Cornerplay-Code", "")):
                    return self._json({"error": "wrong code"}, 403)
                url = urlparse(self.path)
                q = parse_qs(url.query)
                games = {g["key"]: g for g in server.games() if g.get("store") in STORES}
                if url.path == "/games":
                    return self._json({"name": server.name, "games": [
                        {k: g.get(k) for k in ("key", "store", "id", "title", "size")} |
                        {"folder": os.path.basename(g["path"].rstrip("/"))} for g in games.values()]})
                g = games.get((q.get("key") or [""])[0])
                if not g:
                    return self._json({"error": "not here"}, 404)
                if url.path == "/manifest":
                    return self._json({"files": manifest(g["path"])})
                if url.path == "/file":
                    full = inside(g["path"], (q.get("path") or [""])[0])
                    if not full:
                        return self._json({"error": "no such file"}, 404)
                    return self._send_file(full)
                return self._json({"error": "unknown"}, 404)

            def _send_file(self, full):
                size = os.path.getsize(full)
                start = 0
                rng = self.headers.get("Range", "")
                if rng.startswith("bytes="):
                    try:
                        start = max(0, min(size, int(rng[6:].split("-")[0] or 0)))
                    except ValueError:
                        start = 0
                self.send_response(206 if start else 200)
                self.send_header("Content-Length", str(size - start))
                self.send_header("Content-Type", "application/octet-stream")
                self.end_headers()
                with open(full, "rb") as f:
                    f.seek(start)
                    while True:
                        chunk = f.read(1 << 20)
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                        except (BrokenPipeError, ConnectionResetError):
                            return

        self.http = ThreadingHTTPServer(("0.0.0.0", self.port), H)
        self.http.daemon_threads = True
        self.port = self.http.server_address[1]
        threading.Thread(target=self.http.serve_forever, daemon=True, name="lan-share").start()
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp.bind(("0.0.0.0", self.port))
        threading.Thread(target=self._answer, daemon=True, name="lan-hello").start()

    def _answer(self):
        while self.udp:
            try:
                data, addr = self.udp.recvfrom(256)
            except OSError:
                return
            if data == HELLO:
                try:
                    self.udp.sendto(json.dumps({"name": self.name, "port": self.port}).encode(), addr)
                except OSError:
                    pass

    def stop(self):
        if self.http:
            self.http.shutdown()
            self.http.server_close()
            self.http = None
        if self.udp:
            u, self.udp = self.udp, None
            u.close()


# --- the copying PC -------------------------------------------------------------------------
def broadcasts() -> list:
    """Where a "who is there" goes: everyone (255.255.255.255) and each network's own broadcast
    address (192.168.0.255): some systems send the first only out of one network card."""
    import subprocess
    out = ["255.255.255.255"]
    try:
        r = subprocess.run(["ip", "-o", "-4", "addr", "show", "scope", "global"], capture_output=True, text=True, timeout=3)
        for line in r.stdout.splitlines():
            parts = line.split()
            if "brd" in parts:
                out.append(parts[parts.index("brd") + 1])
    except (OSError, subprocess.TimeoutExpired, IndexError):
        pass
    return list(dict.fromkeys(out))


def discover(wait: float = 1.5, port: int = PORT, targets=None) -> list:
    """[{"name", "host", "port"}] of the sharing PCs on this network."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.settimeout(0.3)
    found = {}
    try:
        for addr in targets or broadcasts():
            try:
                s.sendto(HELLO, (addr, port))
            except OSError:
                pass
        end = time.time() + wait
        while time.time() < end:
            try:
                data, addr = s.recvfrom(1024)
            except socket.timeout:
                continue
            try:
                d = json.loads(data)
            except ValueError:
                continue
            if addr[0] not in found and d.get("name"):
                found[addr[0]] = {"name": str(d["name"])[:60], "host": addr[0], "port": int(d.get("port") or port)}
    except OSError:
        pass
    finally:
        s.close()
    return list(found.values())


def _get(host, port, path, code, timeout=10):
    from .net import requests
    r = requests.get(f"http://{host}:{port}{path}", headers={"X-Cornerplay-Code": tidy_code(code)}, timeout=timeout)
    if r.status_code == 403:
        raise PermissionError("wrong code")
    r.raise_for_status()
    return r.json()


def games_on(peer: dict) -> list:
    """The games a linked PC can give ([] when it cannot be reached). Raises PermissionError on a wrong code."""
    try:
        return _get(peer["host"], peer.get("port", PORT), "/games", peer.get("code", ""), timeout=4).get("games") or []
    except PermissionError:
        raise
    except Exception:
        return []


def fetch(host, port, code, key, dest, out=sys.stdout) -> int:
    """Copy one game into dest. Prints "Progress: NN.N%" and speed lines; returns an exit code."""
    from .net import requests
    files = _get(host, port, "/manifest?key=" + quote(key), code)["files"]
    total = sum(f[1] for f in files) or 1
    done = 0
    os.makedirs(dest, exist_ok=True)
    t0, last_print, bytes_since = time.time(), 0.0, 0
    for rel, size, mode, link in files:
        target = os.path.realpath(os.path.join(dest, rel))
        if not target.startswith(os.path.realpath(dest) + os.sep):
            continue  # never outside the game's folder
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if link:
            if not os.path.lexists(target):
                os.symlink(link, target)
            continue
        if os.path.isfile(target) and os.path.getsize(target) == size:
            done += size  # already here (a resumed copy)
            continue
        part = target + ".cornerplay-part"
        have = os.path.getsize(part) if os.path.isfile(part) else 0
        headers = {"X-Cornerplay-Code": tidy_code(code)}
        if have:
            headers["Range"] = f"bytes={have}-"
        r = requests.get(f"http://{host}:{port}/file?key={quote(key)}&path={quote(rel)}", headers=headers,
                         stream=True, timeout=30)
        if r.status_code == 403:
            print("Error: wrong code", file=out, flush=True)
            return 3
        r.raise_for_status()
        if r.status_code == 200:
            have = 0  # the other PC sent the whole file
        done += have
        with open(part, "ab" if have else "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                done += len(chunk)
                bytes_since += len(chunk)
                now = time.time()
                if now - last_print > 1:
                    speed = bytes_since / max(0.001, now - (last_print or t0))
                    print(f"Progress: {100 * done / total:.1f}% ({done}/{total}) "
                          f"Download speed: {speed / 1e6:.2f} MB/s", file=out, flush=True)
                    last_print, bytes_since = now, 0
        if os.path.getsize(part) != size:
            print(f"Error: {rel} came incomplete", file=out, flush=True)
            return 4
        os.chmod(part, mode or 0o644)
        os.replace(part, target)
    print("Progress: 100.0%", file=out, flush=True)
    return 0


def main(argv):
    """fetch HOST PORT KEY DEST [import command...]  (the code comes in CORNERPLAY_LAN_CODE)."""
    if len(argv) < 5 or argv[0] != "fetch":
        print("usage: lancopy fetch HOST PORT KEY DEST [import argv...]", file=sys.stderr)
        return 2
    _cmd, host, port, key, dest, *imp = argv
    try:
        code = fetch(host, int(port), os.environ.get("CORNERPLAY_LAN_CODE", ""), key, dest)
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}", flush=True)
        return 1
    if code == 0 and imp:  # the store learns the game is here (legendary / nile import)
        os.execvp(imp[0], imp)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
