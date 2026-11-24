"""A Proton log, read for you: what went wrong, in a few lines instead of thousands.

A log from "Start with a Proton log" runs to tens of thousands of lines, nearly all of them
Wine's routine notes. read() keeps what matters: where it crashed (the exception and the
program it was in), every Windows library it could not find, the first real errors (the
channels Wine always complains on are left out), graphics errors (DXVK, VKD3D, Vulkan), and
the explanation and fix from problems.py.
"""
import re

from . import problems

ERR = re.compile(r"^\s*(?:[\d.]+:)?(?:[0-9a-f]{4,}:){1,2}err:([\w]+):([\w]*)\s*(.*)$")
MISSING = re.compile(r"(?i)Library (\S+?\.dll) \(which is needed by L?\"?([^\")]*)")
CRASH = re.compile(r"(?i)(?:wine: )?Unhandled (?:exception: )?(page fault[^\n]*|illegal instruction[^\n]*|"
                   r"privileged instruction[^\n]*|exception 0x[0-9a-f]+[^\n]*|stack overflow[^\n]*|"
                   r"c\+\+ exception[^\n]*)")
FRAME0 = re.compile(r"^=>\s*0\s+0x[0-9a-f]+\s+(?:\S+\s+)?in\s+(\S+)(?:\s+\(\+0x([0-9a-f]+)\))?", re.M)
GRAPHICS = re.compile(r"(?i)(VK_ERROR_\w+|DXGI_ERROR_\w+|^\s*err:\s+(?:DXVK|D3D1[12]|Dxvk\w*)[^\n]*"
                      r"|vkd3d[^\n]*err[^\n]*|Failed to create (?:Vulkan|D3D1[12])[^\n]*)", re.M)
# Channels Wine errs on for nearly every game, harmlessly.
NOISE = {"winediag", "systray", "xrandr", "hid", "wineusb", "winebth", "ntoskrnl", "dbghelp", "rawinput",
         "setupapi", "plugplay", "explorer", "winepulse", "mmdevapi", "xinput", "keyboard", "dinput", "seh",
         "openxr"}
# What to install for a missing library, by its name.
DLL_FIX = [(r"^(msvcp|vcruntime|msvcr|concrt|vcomp)1[0-4]\d", "vcrun"), (r"^d3dx(9|10|11)_", "winetricks:d3dx9"),
           (r"^d3dcompiler_", "winetricks:d3dcompiler_47"), (r"^(xactengine|xaudio2_[0-7]|x3daudio)", "winetricks:xact"),
           (r"^(mscoree|clr|mscorlib)", "dotnet")]


def fix_for_dll(name: str) -> str:
    low = (name or "").lower()
    return next((fix for rx, fix in DLL_FIX if re.match(rx, low)), "")


def read(text: str, keep: int = 6) -> dict:
    """{"lines", "crash": {"what", "where", "offset"}, "missing": [{"dll", "by", "fix"}],
    "errors": ["channel: text"], "graphics": [..], "explain": problems.explain()}."""
    text = text or ""
    out = {"lines": text.count("\n"), "crash": {}, "missing": [], "errors": [], "graphics": [], "explain": {}}
    m = CRASH.search(text)
    if m:
        what = re.sub(r",? starting debugger\.*$", "", m.group(1).strip()).rstrip(".")
        crash = {"what": what[:160], "where": "", "offset": ""}
        f = FRAME0.search(text, m.end())
        if f:
            crash["where"], crash["offset"] = f.group(1), f.group(2) or ""
        out["crash"] = crash
    seen = set()
    for dll, by in MISSING.findall(text):
        key = dll.lower()
        if key not in seen:
            seen.add(key)
            out["missing"].append({"dll": dll, "by": by.replace("\\\\", "\\").rsplit("\\", 1)[-1], "fix": fix_for_dll(dll)})
    errs = set()
    for line in text.splitlines():
        e = ERR.match(line)
        if not e or e.group(1) in NOISE:
            continue
        msg = f"{e.group(1)}: {re.sub(r'0x[0-9a-f]{6,}', '0x…', e.group(3))}".strip()[:200]
        if msg not in errs:
            errs.add(msg)
            out["errors"].append(msg)
            if len(out["errors"]) >= keep:
                break
    g = []
    for hit in GRAPHICS.findall(text):
        hit = hit.strip()[:200]
        if hit not in g:
            g.append(hit)
        if len(g) >= keep:
            break
    out["graphics"] = g
    out["explain"] = problems.explain(text)
    return out
