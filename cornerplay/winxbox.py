"""Xbox / PC Game Pass games on Windows: the ones the Xbox app installed.

Each is a Windows app package whose folder holds a MicrosoftGame.config (the GDK's game
manifest: its title, its Store id and the program's application id). One PowerShell call lists
the packages; a game starts as Windows starts it from the Start menu:
    explorer.exe shell:AppsFolder\\<package family name>!<application id>
Installing opens the game's page in the Microsoft Store (the Xbox app takes over from there).
"""
import json
import os
import subprocess
import xml.etree.ElementTree as ET

XBOX_APP = r"shell:AppsFolder\Microsoft.GamingApp_8wekyb3d8bbwe!Microsoft.Xbox.App"

_PS = ("Get-AppxPackage | Where-Object { $_.InstallLocation -and -not $_.IsFramework } | "
       "Select-Object Name, PackageFamilyName, InstallLocation | ConvertTo-Json -Compress")


_cache = (0.0, [])


def _packages() -> list:
    import time
    global _cache
    if time.time() - _cache[0] < 30:  # one refresh asks twice (the app, then the games)
        return _cache[1]
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS],
                           capture_output=True, text=True, timeout=60)
        data = json.loads(r.stdout or "[]")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []
    out = [data] if isinstance(data, dict) else data if isinstance(data, list) else []
    _cache = (time.time(), out)
    return out


def _strip(tag):
    return tag.rsplit("}", 1)[-1]


def parse_config(path: str) -> dict:
    """MicrosoftGame.config: {"title", "storeId", "appId", "exe", "name"} ({} when unreadable)."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return {}
    out = {"title": "", "storeId": "", "appId": "", "exe": "", "name": ""}
    for el in root.iter():
        tag = _strip(el.tag)
        if tag == "Identity" and not out["name"]:
            out["name"] = el.get("Name", "")
        elif tag == "StoreId" and (el.text or "").strip():
            out["storeId"] = el.text.strip()
        elif tag == "Executable" and not out["exe"]:
            out["exe"], out["appId"] = el.get("Name", ""), el.get("Id", "")
        elif tag == "ShellVisuals" and not out["title"]:
            out["title"] = el.get("DefaultDisplayName", "")
    return out


def games() -> list:
    """[{"id" (package family name), "title", "path", "storeId", "appId", "exe"}] for every
    installed GDK game (Xbox app / Game Pass)."""
    out = []
    for p in _packages():
        folder = p.get("InstallLocation") or ""
        cfg = os.path.join(folder, "MicrosoftGame.config")
        if not folder or not os.path.isfile(cfg):
            continue
        info = parse_config(cfg)
        if not info or not info["appId"]:
            continue
        title = info["title"]
        if not title or title.startswith("ms-resource:"):  # a localised name we cannot read here
            title = (p.get("Name") or "").split(".")[-1] or p.get("PackageFamilyName", "")
        out.append({"id": p.get("PackageFamilyName", ""), "title": title, "path": folder,
                    "storeId": info["storeId"], "appId": info["appId"], "exe": info["exe"]})
    return out


def launch_argv(family: str, app_id: str) -> list:
    return ["explorer.exe", rf"shell:AppsFolder\{family}!{app_id}"]


def store_page_argv(store_id: str) -> list:
    """The game's Microsoft Store page, where Install (or Get, with Game Pass) is."""
    return ["explorer.exe", f"ms-windows-store://pdp/?ProductId={store_id}"]


def xbox_app_argv() -> list:
    return ["explorer.exe", XBOX_APP]


def xbox_app_installed() -> bool:
    return any(p.get("Name") == "Microsoft.GamingApp" for p in _packages())
