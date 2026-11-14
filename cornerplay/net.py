"""`requests`, imported on first use.

Importing requests (and urllib3) costs ~0.1 s, and only background downloads need
it, so modules take it from here instead of importing it at startup.
"""


class _LazyRequests:
    def __getattr__(self, name):
        import requests
        return getattr(requests, name)


requests = _LazyRequests()


# ---------------------------------------------------------------- safety helpers
import re as _re

_SECRET_QUERY = _re.compile(r"(?i)([?&](?:key|api_key|apikey|token|access_token|refresh_token|code|client_secret|secret|password)=)[^&\s'\"]+")
_BEARER = _re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+")


def redact(text) -> str:
    """An error message without the secrets that URLs and headers carry (API keys in query
    strings, bearer tokens): requests puts the full URL into its errors, and those reach toasts."""
    return _BEARER.sub(r"\1•••", _SECRET_QUERY.sub(r"\1•••", str(text)))


GITHUB_API = "https://api.github.com/repos/{}/releases/latest"
_ASSET = _re.compile(r'href="/([^"]+?)/releases/download/([^"/]+)/([^"/]+)"|sha256:([0-9a-f]{64})')


def latest_release(repo) -> dict:
    """The newest release of a GitHub repo, shaped like the API's answer ({"tag_name", "assets":
    [{"name", "browser_download_url", "digest"}]}). GitHub's API allows 60 requests an hour per
    internet address, and a shared address (a dorm, an office, mobile data) runs out of them;
    then the same comes from the public release page, digests included."""
    try:
        r = requests.get(GITHUB_API.format(repo), timeout=20, headers={"Accept": "application/vnd.github+json"})
        if r.status_code not in (403, 429):
            r.raise_for_status()
            return r.json()
    except requests.ConnectionError:
        raise
    except Exception:
        pass
    page = requests.get(f"https://github.com/{repo}/releases/latest", timeout=20)
    page.raise_for_status()
    tag = page.url.rstrip("/").rsplit("/tag/", 1)[-1]
    if "/tag/" not in page.url:
        raise RuntimeError(f"{repo} has no release")
    html = requests.get(f"https://github.com/{repo}/releases/expanded_assets/{tag}", timeout=20)
    html.raise_for_status()
    assets, last = [], None
    for m in _ASSET.finditer(html.text):
        if m.group(3):
            name = m.group(3)
            if not any(a["name"] == name for a in assets):
                last = {"name": name, "digest": "",
                        "browser_download_url": f"https://github.com/{m.group(1)}/releases/download/{m.group(2)}/{name}"}
                assets.append(last)
        elif last is not None and not last["digest"]:
            last["digest"] = "sha256:" + m.group(4)  # the page lists each file's digest right after it
    return {"tag_name": tag, "assets": assets}


def github_asset(repo, match):
    """(tag, download url, sha256 or "") of the newest release's asset whose name match(name)
    accepts. GitHub publishes each asset's SHA-256 ("digest"), so downloads can be checked."""
    rel = latest_release(repo)
    for a in rel.get("assets") or []:
        if match(a.get("name", "")):
            digest = a.get("digest") or ""
            return rel.get("tag_name", ""), a["browser_download_url"], digest.split(":", 1)[1] if digest.startswith("sha256:") else ""
    raise RuntimeError(f"No matching download in {repo}'s latest release")


def download_checked(url, dest, sha256="", mode=0o644, progress=None):
    """Download url to dest (atomically). With sha256, a mismatch deletes the file and raises."""
    import hashlib
    import os
    tmp = f"{dest}.part"
    digest = hashlib.sha256()
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0)) or None
        done = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done * 100 / total)
    if sha256 and digest.hexdigest() != sha256.lower():
        os.unlink(tmp)
        raise RuntimeError(f"The download from {url} was damaged or changed (checksum mismatch)")
    os.chmod(tmp, mode)
    os.replace(tmp, dest)
    return str(dest)
