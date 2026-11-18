"""Your year as a short video: a few slides (hours, the most played with their covers, the
busiest month, games started and finished, the longest session), crossfaded into an MP4 by
ffmpeg, in ~/Videos/Cornerplay/. From the stats (desktop: Stats > Your year; TV: Your stats).

Slides are drawn with QPainter on QImages (safe off the UI thread); covers are fetched once.
Needs ffmpeg; without it the slides are kept as PNG pictures instead.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath

from .net import requests

W, H = 1920, 1080
SLIDE = 3.6       # seconds each
FADE = 0.6


def _font(size, bold=True, family="Nunito"):
    f = QFont(family)
    f.setPixelSize(int(size))
    f.setWeight(QFont.Black if bold else QFont.Normal)
    return f


def _canvas(accent):
    img = QImage(W, H, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    g = QLinearGradient(0, 0, W, H)
    a = QColor(accent)
    g.setColorAt(0, QColor("#120f16"))
    g.setColorAt(1, QColor(a.red() // 3, a.green() // 3, a.blue() // 3))
    p.fillRect(0, 0, W, H, g)
    p.setPen(QColor(accent))
    p.setFont(_font(34))
    p.drawText(QRectF(90, 60, W - 180, 60), Qt.AlignLeft | Qt.AlignVCenter, "Cornerplay")
    return img, p


def _text(p, rect, text, size, colour="#f2eee8", bold=True, align=Qt.AlignLeft | Qt.AlignVCenter):
    p.setPen(QColor(colour))
    p.setFont(_font(size, bold))
    p.drawText(QRectF(*rect), align | Qt.TextWordWrap, text)


def _cover(url):
    if not url:
        return None
    try:
        if url.startswith("file://") or os.path.isfile(url):
            img = QImage(url.replace("file://", ""))
        else:
            r = requests.get(url, timeout=10)
            img = QImage()
            img.loadFromData(r.content)
        return None if img.isNull() else img
    except Exception:
        return None


def _draw_cover(p, img, x, y, w, h):
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, y, w, h), 22, 22)
    p.save()
    p.setClipPath(path)
    if img is not None:
        scaled = img.scaled(int(w), int(h), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        p.drawImage(QPointF(x - (scaled.width() - w) / 2, y - (scaled.height() - h) / 2), scaled)
    else:
        p.fillRect(QRectF(x, y, w, h), QColor("#2a2630"))
    p.restore()


def slides(yr, person, accent):
    """The pictures, as QImages, from App.yearStats() (plus "covers": {title: url})."""
    out = []
    year = yr.get("year", "")

    img, p = _canvas(accent)
    _text(p, (90, 300, W - 180, 200), f"{person}'s {year}" if person else str(year), 120)
    _text(p, (90, 520, W - 180, 100), "in games", 64, accent, False)
    p.end()
    out.append(img)

    img, p = _canvas(accent)
    _text(p, (90, 280, W - 180, 260), f"{yr.get('hours', 0):g} hours", 170, accent)
    _text(p, (90, 560, W - 180, 100), f"played across {yr.get('games', 0)} games", 64)
    p.end()
    out.append(img)

    top = (yr.get("top") or [])[:3]
    if top:
        img, p = _canvas(accent)
        _text(p, (90, 150, W - 180, 100), "Most played", 72)
        cw, ch = 360, 525
        gap = 120
        x0 = (W - (len(top) * cw + (len(top) - 1) * gap)) / 2
        for i, t in enumerate(top):
            x = x0 + i * (cw + gap)
            _draw_cover(p, _cover((yr.get("covers") or {}).get(t["title"], "")), x, 300, cw, ch)
            _text(p, (x, 845, cw, 60), t["title"], 36, align=Qt.AlignHCenter | Qt.AlignVCenter)
            _text(p, (x, 905, cw, 50), f"{t['hours']:g} h", 34, accent, False, Qt.AlignHCenter | Qt.AlignVCenter)
        p.end()
        out.append(img)

    months = yr.get("months") or []
    if any(months):
        img, p = _canvas(accent)
        _text(p, (90, 150, W - 180, 100), f"Busiest month: {yr.get('busiestMonth', '')}", 72)
        peak = max(months) or 1
        bw = (W - 180 - 11 * 30) / 12
        for i, m in enumerate(months):
            h = 520 * m / peak
            x = 90 + i * (bw + 30)
            path = QPainterPath()
            path.addRoundedRect(QRectF(x, 880 - h, bw, max(h, 6)), 12, 12)
            p.fillPath(path, QColor(accent) if m == peak else QColor(255, 255, 255, 60))
            _text(p, (x, 900, bw, 50), "JFMAMJJASOND"[i], 30, "#a59f99", False, Qt.AlignHCenter | Qt.AlignVCenter)
        p.end()
        out.append(img)

    if yr.get("newCount") or yr.get("finishedCount"):
        img, p = _canvas(accent)
        _text(p, (90, 220, W / 2 - 120, 200), f"{yr.get('newCount', 0)}", 180, accent)
        _text(p, (90, 440, W / 2 - 120, 80), "started for the first time", 46)
        _text(p, (W / 2 + 30, 220, W / 2 - 120, 200), f"{yr.get('finishedCount', 0)}", 180, accent)
        _text(p, (W / 2 + 30, 440, W / 2 - 120, 80), "finished", 46)
        names = ", ".join((yr.get("finished") or [])[:4])
        if names:
            _text(p, (90, 640, W - 180, 200), "Finished: " + names, 40, "#cfc8c0", False, Qt.AlignLeft | Qt.AlignTop)
        p.end()
        out.append(img)

    longest = yr.get("longest") or {}
    if longest.get("title"):
        img, p = _canvas(accent)
        _text(p, (90, 220, W - 180, 100), "Longest session", 64, accent)
        _text(p, (90, 360, W - 180, 260), longest["title"], 110)
        _text(p, (90, 640, W - 180, 100), f"{longest.get('hours', 0):g} hours, {longest.get('date', '')}", 56, "#cfc8c0", False)
        p.end()
        out.append(img)

    img, p = _canvas(accent)
    _text(p, (90, 380, W - 180, 200), f"See you in {int(year) + 1 if str(year).isdigit() else 'the next one'}", 110,
          align=Qt.AlignHCenter | Qt.AlignVCenter)
    p.end()
    out.append(img)
    return out


def make(yr, person, accent, out_dir):
    """Write the video (or the pictures without ffmpeg). Returns (path, error)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pics = slides(yr, person, accent)
    work = Path(tempfile.mkdtemp(prefix="cp-recap-"))
    try:
        files = []
        for i, img in enumerate(pics):
            f = work / f"{i:02d}.png"
            img.save(str(f))
            files.append(f)
        name = f"Cornerplay {yr.get('year', '')}" + (f" - {person}" if person else "")
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            folder = out_dir / name
            folder.mkdir(exist_ok=True)
            for f in files:
                shutil.copy(f, folder / f.name)
            return str(folder), "ffmpeg is not installed: the pictures are in the folder instead"
        argv = [ffmpeg, "-y", "-loglevel", "error"]
        for f in files:
            argv += ["-loop", "1", "-t", f"{SLIDE}", "-i", str(f)]
        chain, last = [], "[0:v]"
        for i in range(1, len(files)):
            tag = f"[v{i}]"
            chain.append(f"{last}[{i}:v]xfade=transition=fade:duration={FADE}:offset={i * (SLIDE - FADE):.2f}{tag}")
            last = tag
        filt = ";".join(chain + [f"{last}format=yuv420p,fps=30[out]"])
        target = out_dir / f"{name}.mp4"
        argv += ["-filter_complex", filt, "-map", "[out]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                 "-movflags", "+faststart", str(target)]
        r = subprocess.run(argv, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            return "", (r.stderr or "ffmpeg failed").strip().splitlines()[-1][:200]
        return str(target), ""
    finally:
        shutil.rmtree(work, ignore_errors=True)
