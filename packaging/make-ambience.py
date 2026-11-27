"""Write cornerplay/sounds/rain.ogg and fire.ogg: the desktop's optional background sounds.

Both are made here from noise (no recordings): every layer is shaped in the frequency domain
or added with wrap-round, so each file loops with no seam.
    python3 packaging/make-ambience.py      (needs numpy and ffmpeg)
"""
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

RATE = 44100
SECONDS = 40
N = RATE * SECONDS


def shaped(rng, curve):
    """Looping noise with the spectrum curve(freqs) (circular, so it has no seam)."""
    spec = np.fft.rfft(rng.standard_normal(N))
    f = np.fft.rfftfreq(N, 1 / RATE)
    out = np.fft.irfft(spec * curve(np.maximum(f, 1.0)), N)
    return out / np.max(np.abs(out))


def add(buf, start, sig):
    i = start % len(buf)
    first = min(len(sig), len(buf) - i)
    buf[i:i + first] += sig[:first]
    if first < len(sig):
        add(buf, 0, sig[first:])


def slow_wobble(rng, period_s, depth):
    """A gentle level change that loops: a few sines whose periods divide the file length."""
    t = np.arange(N) / RATE
    w = np.ones(N)
    for k in (1, 2, 3):
        cycles = max(1, round(SECONDS / period_s) * k)
        w += depth / k * np.sin(2 * np.pi * cycles * t / SECONDS + rng.uniform(0, 6.28))
    return w


def rain(rng):
    # The steady hiss of rain on a window: pink-ish noise, dulled above ~6 kHz.
    bed = shaped(rng, lambda f: f ** -0.45 / (1 + (f / 6000) ** 2) * (f > 120))
    bed *= slow_wobble(rng, 11, 0.12)
    # Drops: tiny bright ticks, a few hundred a second, and now and then a fat one on the sill.
    drops = np.zeros(N)
    for _ in range(SECONDS * 260):
        n = int(RATE * rng.uniform(0.002, 0.006))
        t = np.arange(n) / RATE
        tone = np.sin(2 * np.pi * rng.uniform(2500, 6000) * t) * np.exp(-t * rng.uniform(900, 1600))
        add(drops, int(rng.uniform(0, N)), tone * rng.uniform(0.05, 0.25))
    for _ in range(SECONDS * 3):
        n = int(RATE * 0.05)
        t = np.arange(n) / RATE
        f0 = rng.uniform(600, 1300)
        plop = np.sin(2 * np.pi * (f0 + 900 * np.exp(-t * 60)) * t) * np.exp(-t * 70)
        add(drops, int(rng.uniform(0, N)), plop * rng.uniform(0.15, 0.35))
    return 0.55 * bed + 0.6 * drops


def fire(rng):
    # The soft roar of a fire: brown-ish noise, deep and breathing.
    roar = shaped(rng, lambda f: f ** -0.9 / (1 + (f / 900) ** 2) * (f > 40))
    roar *= slow_wobble(rng, 6, 0.3)
    # Crackles and pops: clusters of sharp clicks, then a quiet spell.
    crack = np.zeros(N)
    pos = 0
    while pos < N:
        pos += int(RATE * rng.exponential(0.35))
        for _ in range(rng.integers(1, 7)):
            n = int(RATE * rng.uniform(0.001, 0.004))
            click = rng.standard_normal(n) * np.exp(-np.arange(n) / (n / 4))
            add(crack, pos + int(RATE * rng.uniform(0, 0.08)), click * rng.uniform(0.1, 0.6))
    # A small hiss of sap now and then.
    hiss = shaped(rng, lambda f: (f > 2500) / (1 + (f / 8000) ** 2))
    gate = np.zeros(N)
    for _ in range(SECONDS // 5):
        n = int(RATE * rng.uniform(0.6, 1.5))
        add(gate, int(rng.uniform(0, N)), np.sin(np.linspace(0, np.pi, n)) * 0.08)
    return 0.8 * roar + 0.55 * crack + hiss * gate


def write(sig, out):
    sig = sig / np.max(np.abs(sig)) * 0.7
    pcm = (sig * 32767).astype("<i2")
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "x.wav"
        with wave.open(str(wav), "wb") as w:  # mono: quiet background sound, and a small installer
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(pcm.tobytes())
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-c:a", "libvorbis", "-q:a", "0", "-ar", "32000",
                        str(out)], check=True)


def main(folder):
    for name, make, seed in (("rain", rain, 7), ("fire", fire, 11)):
        write(make(np.random.default_rng(seed)), folder / f"{name}.ogg")
        print("wrote", folder / f"{name}.ogg")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "cornerplay" / "sounds")
