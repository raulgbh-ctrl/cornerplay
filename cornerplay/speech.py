"""Reading TV mode aloud (Accessibility > Read aloud): what is selected is said as it is
selected, cutting off what was being said. Qt's text-to-speech (speech-dispatcher or flite),
else espeak-ng or spd-say. Nothing installed: available() says so and say() does nothing.
"""
import shutil
import subprocess

_tts = None
_tried = False
_proc = None


def _engine():
    global _tts, _tried
    if _tried:
        return _tts
    _tried = True
    try:
        from PySide6.QtTextToSpeech import QTextToSpeech
    except ImportError:
        return None
    for name in ("speechd", "flite"):
        if name not in QTextToSpeech.availableEngines():
            continue
        t = QTextToSpeech(name)
        if t.state() != QTextToSpeech.State.Error:
            _tts = t
            return t
    return None


def available() -> bool:
    return _engine() is not None or bool(shutil.which("espeak-ng") or shutil.which("spd-say"))


def say(text: str):
    global _proc
    t = _engine()
    if t is not None:
        t.stop()
        t.say(text)
        return
    if _proc and _proc.poll() is None:
        _proc.terminate()
    if not shutil.which("espeak-ng") and shutil.which("spd-say"):
        subprocess.run(["spd-say", "-C"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
    cmd = ["espeak-ng", "-s", "170", text] if shutil.which("espeak-ng") else \
          ["spd-say", text] if shutil.which("spd-say") else None
    if cmd:
        try:
            _proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            _proc = None
