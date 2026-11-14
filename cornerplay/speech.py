"""Reading TV mode aloud (Accessibility > Read aloud): what is selected is said as it is
selected, cutting off what was being said.

Voices, in order: Qt's text-to-speech (speech-dispatcher or flite) when the system has one,
espeak-ng or spd-say on the PATH, else Cornerplay's own copy of eSpeak NG: the library and
its voices from the espeakng-loader package on PyPI (a manylinux build, every language
eSpeak has, Romanian included), pinned and checked against its SHA-256, downloaded into
~/.local/share/cornerplay/speech on request (no root). It speaks into PipeWire (pw-cat) or
PulseAudio (paplay).
"""
import ctypes
import io
import os
import shutil
import subprocess
import threading
import zipfile

from .config import DATA_DIR, settings

PRIVATE = DATA_DIR / "speech"
LIB = PRIVATE / "espeakng_loader" / "libespeak-ng.so.1"
WHEEL_URL = ("https://files.pythonhosted.org/packages/de/1e/25ec5ab07528c0fbb215a61800a38eca05c8a99445515a02d7fa5debcb32/"
             "espeakng_loader-0.2.4-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl")
WHEEL_SHA256 = "08721baf27d13d461f6be6eed9a65277e70d68234ff484fd8b9897b222cdcb6d"

_tts = None
_tried = False
_proc = None
_lock = threading.Lock()
_esp = None          # (library, sample rate, callback) once loaded
_buf = []
_voice = ""


def _qt_engine():
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


def _player():
    return shutil.which("pw-cat") or shutil.which("paplay")


def private_ready() -> bool:
    return LIB.is_file() and bool(_player())


def available() -> bool:
    return _qt_engine() is not None or bool(shutil.which("espeak-ng") or shutil.which("spd-say")) or private_ready()


def can_fetch() -> bool:
    return os.uname().machine == "x86_64" and bool(_player())


def fetch() -> str:
    """Download the pinned eSpeak NG build, check it, unpack it. Returns the library's path."""
    import hashlib
    from .net import requests
    if not can_fetch():
        raise RuntimeError("A voice can be downloaded only on x86_64 with PipeWire or PulseAudio; install espeak-ng instead")
    r = requests.get(WHEEL_URL, timeout=180)
    r.raise_for_status()
    if hashlib.sha256(r.content).hexdigest() != WHEEL_SHA256:
        raise RuntimeError("The voice download was damaged or changed (checksum mismatch)")
    tmp = PRIVATE.with_suffix(".part")
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for m in z.namelist():
            if m.startswith("espeakng_loader/") and ".." not in m:
                z.extract(m, tmp)
    shutil.rmtree(PRIVATE, ignore_errors=True)
    os.replace(tmp, PRIVATE)
    return str(LIB)


def _language():
    lang = (settings.get("language") or os.environ.get("LANG", "en"))[:2].lower()
    return lang if lang in ("ro", "en", "de", "fr", "es", "it", "pt", "nl", "pl", "hu") else "en"


def _load():
    global _esp
    if _esp is not None:
        return _esp
    lib = ctypes.CDLL(str(LIB))
    lib.espeak_Initialize.restype = ctypes.c_int
    lib.espeak_Initialize.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    rate = lib.espeak_Initialize(2, 0, str(LIB.parent).encode(), 0)  # 2: synchronous, into our callback
    if rate <= 0:
        raise OSError("eSpeak NG did not start")
    cb_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)

    def cb(wav, n, _events):
        if n > 0:
            _buf.append(ctypes.string_at(wav, n * 2))
        return 0
    callback = cb_type(cb)
    lib.espeak_SetSynthCallback(callback)
    lib.espeak_SetParameter.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.espeak_SetParameter(1, 185, 0)  # espeakRATE: words a minute
    lib.espeak_Synth.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_int, ctypes.c_uint,
                                 ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    _esp = (lib, rate, callback)
    return _esp


def _private_say(text):
    global _proc, _voice
    with _lock:
        lib, rate, _cb = _load()
        lang = _language()
        if lang != _voice:
            lib.espeak_SetVoiceByName(lang.encode())
            _voice = lang
        _buf.clear()
        data = text.encode()
        lib.espeak_Synth(data, len(data) + 1, 0, 1, 0, 1, None, None)  # 1: by character, UTF-8
        pcm = b"".join(_buf)
        if _proc and _proc.poll() is None:
            _proc.terminate()
        player = _player()
        cmd = ([player, "--playback", "--raw", "--rate", str(rate), "--channels", "1", "--format", "s16", "-"]
               if player.endswith("pw-cat") else [player, "--raw", f"--rate={rate}", "--channels=1", "--format=s16le"])
        try:
            _proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _proc.stdin.write(pcm)
            _proc.stdin.close()
        except (OSError, BrokenPipeError):
            _proc = None


def say(text: str):
    global _proc
    t = _qt_engine()
    if t is not None:
        t.stop()
        t.say(text)
        return
    if shutil.which("espeak-ng") or shutil.which("spd-say"):
        if _proc and _proc.poll() is None:
            _proc.terminate()
        if not shutil.which("espeak-ng"):
            subprocess.run(["spd-say", "-C"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        cmd = ["espeak-ng", "-v", _language(), "-s", "175", text] if shutil.which("espeak-ng") else ["spd-say", text]
        try:
            _proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            _proc = None
        return
    if private_ready():
        threading.Thread(target=_private_say, args=(text,), daemon=True, name="say").start()
