"""Fetch what the Windows build ships next to Cornerplay.exe, each checked against its SHA-256:
legendary, gogdl and nile (their newest Windows releases, checksums from GitHub) into
extra/backends, and SDL2.dll (the pinned pysdl2-dll release in cornerplay/sdl.py) into extra.

    python packaging/windows/fetch_extras.py
"""
import hashlib
import io
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from cornerplay.config import BACKEND_REPOS  # noqa: E402
from cornerplay.net import download_checked, github_asset, requests  # noqa: E402

# The Windows wheel of the same pysdl2-dll release cornerplay/sdl.py pins.
SDL_URL = ("https://files.pythonhosted.org/packages/91/8e/3a90c664cca4c61c7538a8b1a7fd86c7dc3521465198a844bce21b4a97c1/"
           "pysdl2_dll-2.32.10-py2.py3-none-win_amd64.whl")
SDL_SHA256 = "65eba83d68c33b22aa5eca6c9a8521cff5044435ecd5b49521068df82674de6a"


def main():
    extra = os.path.join(HERE, "extra")
    backends = os.path.join(extra, "backends")
    os.makedirs(backends, exist_ok=True)
    for name, repo in BACKEND_REPOS.items():
        asset = f"{name}_windows_x86_64.exe"
        tag, url, sha = github_asset(repo, lambda n, asset=asset: n == asset)
        if not sha:
            raise SystemExit(f"{name}: GitHub lists no checksum for {asset}; not shipping it unchecked")
        path = download_checked(url, os.path.join(backends, f"{name}.exe"), sha)
        print(f"{name} {tag}: {path}")
    r = requests.get(SDL_URL, timeout=120)
    r.raise_for_status()
    if hashlib.sha256(r.content).hexdigest() != SDL_SHA256:
        raise SystemExit("SDL2: checksum mismatch")
    dll = zipfile.ZipFile(io.BytesIO(r.content)).read("sdl2dll/dll/SDL2.dll")
    with open(os.path.join(extra, "SDL2.dll"), "wb") as f:
        f.write(dll)
    print(f"SDL2.dll: {len(dll)} bytes")


if __name__ == "__main__":
    main()
