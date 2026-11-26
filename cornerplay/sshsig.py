"""Checking a release's signature without ssh-keygen (Windows has none by default).

Releases are signed with `ssh-keygen -Y sign` (tools/sign-release.sh): an "SSH signature"
(OpenSSH's PROTOCOL.sshsig) made with an Ed25519 key. This reads that format and checks the
Ed25519 signature with the reference arithmetic of RFC 8032 (verification only: no secrets here),
so every copy of Cornerplay checks its updates the same way, whatever the system has installed.
"""
import base64
import hashlib
import struct

# --- Ed25519 (RFC 8032, section 5.1), verification only -------------------------------------------
_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_I = pow(2, (_P - 1) // 4, _P)  # a square root of -1


def _add(a, b):
    x1, y1, z1, t1 = a
    x2, y2, z2, t2 = b
    A = (y1 - x1) * (y2 - x2) % _P
    B = (y1 + x1) * (y2 + x2) % _P
    C = 2 * t1 * t2 * _D % _P
    D = 2 * z1 * z2 % _P
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _P, G * H % _P, F * G % _P, E * H % _P)


def _mul(s, point):
    q = (0, 1, 1, 0)  # neutral
    while s > 0:
        if s & 1:
            q = _add(q, point)
        point = _add(point, point)
        s >>= 1
    return q


def _equal(a, b):
    x1, y1, z1, _ = a
    x2, y2, z2, _ = b
    return (x1 * z2 - x2 * z1) % _P == 0 and (y1 * z2 - y2 * z1) % _P == 0


def _x_from_y(y, sign):
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _I % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


def _decode(b):
    if len(b) != 32:
        return None
    y = int.from_bytes(b, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _x_from_y(y, sign)
    return None if x is None else (x, y, 1, x * y % _P)


_G = (_x_from_y(4 * pow(5, _P - 2, _P) % _P, 0), 4 * pow(5, _P - 2, _P) % _P, 1, 0)
_G = (_G[0], _G[1], 1, _G[0] * _G[1] % _P)


def ed25519_verify(public: bytes, message: bytes, signature: bytes) -> bool:
    if len(public) != 32 or len(signature) != 64:
        return False
    A = _decode(public)
    R = _decode(signature[:32])
    if A is None or R is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _L:
        return False
    k = int.from_bytes(hashlib.sha512(signature[:32] + public + message).digest(), "little") % _L
    return _equal(_mul(s, _G), _add(R, _mul(k, A)))


# --- OpenSSH's signature format (PROTOCOL.sshsig) ---------------------------------------------------
def _strings(data: bytes):
    """The length-prefixed strings an SSH blob is made of."""
    out, i = [], 0
    while i < len(data):
        if i + 4 > len(data):
            raise ValueError("truncated")
        (n,) = struct.unpack(">I", data[i:i + 4])
        if i + 4 + n > len(data):
            raise ValueError("truncated")
        out.append(data[i + 4:i + 4 + n])
        i += 4 + n
    return out


def _string(b: bytes) -> bytes:
    return struct.pack(">I", len(b)) + b


def verify(public_key_line: str, namespace: str, armored_signature: str, file_path) -> bool:
    """True when armored_signature (the .sig file's text) is public_key_line's ("ssh-ed25519 AAAA...")
    signature, in namespace, of the file at file_path."""
    try:
        key_blob = base64.b64decode(public_key_line.split()[1])
        kind, pub = _strings(key_blob)
        if kind != b"ssh-ed25519":
            return False
        body = "".join(line.strip() for line in armored_signature.strip().splitlines()
                       if line.strip() and not line.startswith("-----"))
        blob = base64.b64decode(body)
        if blob[:6] != b"SSHSIG":
            return False
        (version,) = struct.unpack(">I", blob[6:10])
        signed_key, ns, reserved, hash_alg, sig = _strings(blob[10:])
        if version != 1 or signed_key != key_blob or ns != namespace.encode() or hash_alg not in (b"sha512", b"sha256"):
            return False
        sig_kind, raw = _strings(sig)
        if sig_kind != b"ssh-ed25519":
            return False
        h = hashlib.new(hash_alg.decode())
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        signed = b"SSHSIG" + _string(ns) + _string(reserved) + _string(hash_alg) + _string(h.digest())
        return ed25519_verify(pub, signed, raw)
    except (ValueError, IndexError, struct.error, OSError):
        return False
