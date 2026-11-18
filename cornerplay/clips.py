"""Clips: the last 30 seconds of a game, saved on demand (gpu-screen-recorder's replay buffer).

While a game started from Cornerplay runs (Settings > Games: clips), gpu-screen-recorder keeps
the last CLIP_SECONDS in memory; "Save a clip" (quick access over a game, Guide + A, or TV mode's
quick access) sends it SIGUSR1 and it writes an .mp4 to ~/Videos/Cornerplay/<game>/.
Nothing is written unless asked. On Wayland the screen comes through KMS (gpu-screen-recorder's
gsr-kms-server, set up by its package). Without a hardware video encoder (no VA-API) it encodes
on the CPU.
"""
import os
import re
import shutil
import signal
import subprocess
from pathlib import Path

CLIP_SECONDS = 30


def available() -> bool:
    return bool(shutil.which("gpu-screen-recorder"))


def folder(title: str) -> Path:
    videos = os.environ.get("XDG_VIDEOS_DIR") or str(Path.home() / "Videos")
    safe = re.sub(r'[\\/:*?"<>|]+', " ", title or "Game").strip() or "Game"
    return Path(videos) / "Cornerplay" / safe


def start(title: str):
    """Start the replay buffer for a game. Returns the process, or None."""
    if not available():
        return None
    out = folder(title)
    out.mkdir(parents=True, exist_ok=True)
    argv = ["gpu-screen-recorder", "-w", "screen", "-f", "60", "-c", "mp4", "-r", str(CLIP_SECONDS),
            "-a", "default_output", "-fallback-cpu-encoding", "yes", "-o", str(out)]
    try:
        return subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return None


def save(proc) -> bool:
    """Write the last CLIP_SECONDS to the game's folder."""
    if proc is None or proc.poll() is not None:
        return False
    try:
        os.kill(proc.pid, signal.SIGUSR1)
        return True
    except OSError:
        return False


def stop(proc):
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGINT)
        proc.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
