"""Shared helpers of the E1 probe: GoZ folders, text files, atomic writes, process checks and the comparison of a
received GoZ file with what was sent (README §2.2, §5, §7). Stdlib only; no pyglet, no `Application`."""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from goz_probe._paths import EXPERIMENT_DIR
from goz_probe.goz_probe_format import GozFile, as_float32

APP_FOLDER_NAME = "MiraiProbe"  # the GoZ application id: no spaces (SDK IV)
APP_DISPLAY_NAME = "Mirai Probe (E1)"
APP_MARKER = ".mirai_goz_probe"  # proves a GoZApps folder is ours before --replace / --uninstall touch it
DEFAULT_CAPTURES = EXPERIMENT_DIR / "captures"
DEFAULT_INBOX = EXPERIMENT_DIR / "inbox"
DEFAULT_MESHES = EXPERIMENT_DIR / "meshes"
IS_WINDOWS = os.name == "nt"


class ProbeError(RuntimeError):
    pass


# -- GoZ folders -------------------------------------------------------------------------------------------------------


def root_candidates() -> list[Path]:
    """Windows GoZ roots, in the order they are tried: the SDK's `C:\\Users\\Public\\Pixologic` (ZBrush 2022), then a
    Maxon-era location (newer versions)."""
    public = Path(os.environ.get("PUBLIC", r"C:\Users\Public"))
    return [public / "Pixologic", public / "Documents" / "Maxon", public / "Maxon"]


def find_root(explicit: Optional[str | os.PathLike] = None) -> Path:
    """`--root`, else `MIRAI_GOZ_ROOT`, else the first candidate that has a `GoZBrush` folder."""
    if explicit:
        return Path(explicit)
    env = os.environ.get("MIRAI_GOZ_ROOT")
    if env:
        return Path(env)
    for candidate in root_candidates():
        if (candidate / "GoZBrush").is_dir():
            return candidate
    raise ProbeError(
        "no GoZ root found (looked for a GoZBrush folder in: "
        + ", ".join(str(c) for c in root_candidates())
        + "). Start ZBrush once, or pass --root."
    )


@dataclass(frozen=True)
class GozPaths:
    root: Path

    @property
    def gozbrush(self) -> Path:
        return self.root / "GoZBrush"

    @property
    def apps(self) -> Path:
        return self.root / "GoZApps"

    @property
    def app_dir(self) -> Path:
        return self.apps / APP_FOLDER_NAME

    @property
    def object_list(self) -> Path:
        return self.gozbrush / "GoZ_ObjectList.txt"

    @property
    def application_file(self) -> Path:
        return self.gozbrush / "GoZ_Application.txt"

    @property
    def project_path_file(self) -> Path:
        return self.gozbrush / "GoZ_ProjectPath.txt"

    @property
    def object_path_file(self) -> Path:
        return self.gozbrush / "GoZ_ObjectPath.txt"

    @property
    def config_file(self) -> Path:
        return self.gozbrush / "GoZ_Config.txt"

    def utility(self, name: str) -> Path:
        return self.gozbrush / (name + (".exe" if IS_WINDOWS else ""))

    def project_dir(self) -> Path:
        text = read_text(self.project_path_file)
        line = text.strip().splitlines()[0].strip() if text and text.strip() else ""
        return Path(line) if line else self.root / "GoZProjects" / "Default"


# -- text files --------------------------------------------------------------------------------------------------------


def ansi_encoding() -> str:
    return "mbcs" if IS_WINDOWS else "utf-8"


def read_text(path: Path) -> Optional[str]:
    """A GoZ text file, or None if missing. ZBrush is a C program: try UTF-8, then the ANSI code page, then latin-1."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    for encoding in ("utf-8-sig", ansi_encoding(), "latin-1"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("latin-1", errors="replace")


def read_pff(path: Path) -> dict[str, str]:
    """`KEY = value` per line (SDK appendix V); quotes ("", “”, '') around the value are removed."""
    prefs: dict[str, str] = {}
    for line in (read_text(path) or "").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"\u201c\u201d\'')
        prefs[key.strip()] = value
    return prefs


def read_object_list(path: Path) -> list[str]:
    """The identifiers of `GoZ_ObjectList.txt` (one per line, no extension); an empty list is one empty line."""
    return [line.strip() for line in (read_text(path) or "").splitlines() if line.strip()]


def write_text_atomic(path: Path, text: str, *, encoding: Optional[str] = None, newline: str = "\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with open(tmp, "w", encoding=encoding or "utf-8", newline=newline) as handle:
        handle.write(text)
    os.replace(tmp, path)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write_json_atomic(path: Path, value) -> None:
    write_text_atomic(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def write_goz_text(path: Path, lines: Sequence[str]) -> None:
    """A GoZ list file as Windows programs write it: ANSI, CRLF, one line per entry, one empty line for none."""
    text = "\r\n".join(lines) + "\r\n" if lines else "\r\n"
    write_text_atomic(path, text, encoding=ansi_encoding(), newline="")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stat_record(path: Path) -> dict:
    try:
        st = path.stat()
    except FileNotFoundError:
        return {"exists": False}
    return {"exists": True, "size": st.st_size, "mtime_ns": st.st_mtime_ns}


def timestamp(ns: Optional[int] = None) -> str:
    ns = time.time_ns() if ns is None else ns
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(ns / 1e9)) + f"_{(ns // 1_000_000) % 1000:03d}"


def new_capture_dir(captures: Path, suffix: str, ns: Optional[int] = None) -> Path:
    base = captures / f"{timestamp(ns)}_{suffix}"
    path, n = base, 2
    while path.exists():
        path = base.with_name(f"{base.name}_{n}")
        n += 1
    path.mkdir(parents=True)
    return path


def redact(value):
    """Replaces the Windows user profile path and user name (`USERPROFILE`, `USERNAME`) in every string value
    (recursively; keys stay). The profile only as a whole path prefix, the name only as a whole path component, so
    `C:\\Users\\Manuel2` or the word `Manuelle` stay as they are. Without those variables (Linux) nothing changes."""
    profile = os.environ.get("USERPROFILE", "")
    user = os.environ.get("USERNAME", "")
    profile_re = (
        re.compile(r"(?<![\w\\/.:-])" + re.escape(profile.rstrip("\\/")) + r"(?=[\\/]|$|[\"'\]\s])", re.IGNORECASE)
        if len(profile) > 3 else None
    )
    user_re = re.compile(r"(?<=[\\/])" + re.escape(user) + r"(?=[\\/]|$)", re.IGNORECASE) if len(user) > 1 else None

    def fix(v):
        if isinstance(v, str):
            if profile_re:
                v = profile_re.sub("%USERPROFILE%", v)
            return user_re.sub("%USERNAME%", v) if user_re else v
        if isinstance(v, dict):
            return {k: fix(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [fix(x) for x in v]
        return v

    return fix(value)


# -- processes and file locks -------------------------------------------------------------------------------------------


_KERNEL32 = None


def kernel32():
    """A private, fully typed kernel32 (Windows only): explicit argtypes keep 64-bit handles and DWORD flags intact."""
    global _KERNEL32
    if _KERNEL32 is None:
        import ctypes
        from ctypes import wintypes

        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k.GetExitCodeProcess.restype = wintypes.BOOL
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        k.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
            wintypes.HANDLE,
        ]
        k.CreateFileW.restype = wintypes.HANDLE
        k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k.GetOEMCP.restype = wintypes.UINT
        _KERNEL32 = k
    return _KERNEL32


INVALID_HANDLE = (1 << (8 * ctypes.sizeof(ctypes.c_void_p))) - 1  # (HANDLE)-1 as ctypes returns it


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if IS_WINDOWS:
        import ctypes
        from ctypes import wintypes

        k = kernel32()
        handle = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            return bool(k.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
        finally:
            k.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def exclusive_open(path: Path) -> str:
    """Windows: open with share mode 0 - succeeds only while no other process holds the file ("ok", or "blocked
    (error N)", 32 = sharing violation). Elsewhere "n/a". Diagnostic only (README §7.5)."""
    if not IS_WINDOWS:
        return "n/a"
    import ctypes

    k = kernel32()
    handle = k.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)  # GENERIC_READ, no sharing, OPEN_EXISTING
    if handle is None or handle == INVALID_HANDLE:
        return f"blocked (error {ctypes.get_last_error()})"
    k.CloseHandle(handle)
    return "ok"


# -- sent meshes and the comparison ---------------------------------------------------------------------------------------


def load_sent(meshes: Path) -> dict[str, dict]:
    sent = {}
    for path in sorted(meshes.glob("*.sent.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        sent[data["id"]] = data
    return sent


def match_sent(goz: GozFile, identifier: str, sent: dict[str, dict], send_logs: Iterable[dict]) -> tuple[Optional[dict], str]:
    """Which sent mesh a received file is: by an earlier `probe_send` identifier, else by counts (a ZBrush OBJ import of
    `meshes/<id>.obj` keeps its counts), else by name."""
    for log in send_logs:
        if log.get("identifier") and Path(log["identifier"]).name == Path(identifier).name and log.get("mesh") in sent:
            return sent[log["mesh"]], f"identifier of the send log {log.get('log_dir')}"
    by_counts = [s for s in sent.values() if len(s["positions"]) == len(goz.points) and len(s["faces"]) == len(goz.faces)]
    if len(by_counts) == 1:
        return by_counts[0], "vertex and face counts"
    names = {goz.name or "", Path(identifier).name}
    for s in sent.values():
        if names & {s["name"], f"E1_{s['id']}", f"GoZMesh_{s['name']}"}:
            return s, "name"
    return None, "no match"


def _regress(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float, float]:
    n = len(xs)
    mx, my = math.fsum(xs) / n, math.fsum(ys) / n
    sxx = math.fsum((x - mx) ** 2 for x in xs)
    syy = math.fsum((y - my) ** 2 for y in ys)
    sxy = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0.0 or syy == 0.0:
        return 0.0, 0.0, my
    a = sxy / sxx
    return sxy / math.sqrt(sxx * syy), a, my - a * mx


def _bbox(points: Sequence[Sequence[float]]) -> tuple[list[float], list[float]]:
    return [min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)]


AXES = "xyz"


def axis_mapping(sent: Sequence[Sequence[float]], received: Sequence[Sequence[float]], same_order: bool) -> list[dict]:
    """Per received axis j: the sent axis i, factor a and offset b with `received_j ≈ a·sent_i + b`. With the same vertex
    order a regression per axis pair; otherwise from the bounding boxes (needs distinct extents, test mesh A has them)."""
    result = []
    if same_order and len(sent) == len(received) and len(sent) > 1:
        for j in range(3):
            ys = [p[j] for p in received]
            best = max(
                ((i,) + _regress([p[i] for p in sent], ys) for i in range(3)), key=lambda t: abs(t[1])
            )
            i, corr, a, b = best
            result.append({"axis": AXES[j], "from": AXES[i], "factor": a, "offset": b, "corr": corr, "method": "regression"})
        if min(abs(r["corr"]) for r in result) > 0.999:
            return result
        # the vertices do not correspond one to one after all (e.g. reordered points): fall back to the bounding boxes
        result = []
    lo_s, hi_s = _bbox(sent)
    lo_r, hi_r = _bbox(received)
    ext_s = [h - l for l, h in zip(lo_s, hi_s)]
    ext_r = [h - l for l, h in zip(lo_r, hi_r)]
    order_s = sorted(range(3), key=lambda i: ext_s[i])
    order_r = sorted(range(3), key=lambda j: ext_r[j])
    for rank in range(3):
        i, j = order_s[rank], order_r[rank]
        scale = ext_r[j] / ext_s[i] if ext_s[i] else 0.0
        c_s, c_r = (lo_s[i] + hi_s[i]) / 2, (lo_r[j] + hi_r[j]) / 2
        sign = 1.0 if abs(c_r - scale * c_s) <= abs(c_r + scale * c_s) else -1.0
        a = sign * scale
        result.append({"axis": AXES[j], "from": AXES[i], "factor": a, "offset": c_r - a * c_s, "corr": None, "method": "bbox"})
    return sorted(result, key=lambda r: AXES.index(r["axis"]))


def _rotation_equal(a: Sequence[int], b: Sequence[int]) -> bool:
    if len(a) != len(b):
        return False
    return any(list(a[k:]) + list(a[:k]) == list(b) for k in range(len(a)))


def analyse(goz: GozFile, sent: dict) -> dict:
    """The E1 comparison of a received file with the mesh that was sent (README T2, T5, T6)."""
    # GoZ carries float32: compare against the float32 values of what was sent, so an exact mapping measures exactly.
    sent_points = [tuple(as_float32(c) for c in p) for p in sent["positions"]]
    sent_faces = [tuple(f) for f in sent["faces"]]
    out: dict = {
        "sent_id": sent["id"],
        "counts": {"sent": [len(sent_points), len(sent_faces)], "received": [len(goz.points), len(goz.faces)]},
    }
    same_counts = len(sent_points) == len(goz.points) and len(sent_faces) == len(goz.faces)
    if same_counts:
        identical = sum(1 for a, b in zip(sent_faces, goz.faces) if tuple(a) == tuple(b))
        rotated = sum(1 for a, b in zip(sent_faces, goz.faces) if tuple(a) != tuple(b) and _rotation_equal(a, b))
        reversed_ = sum(
            1 for a, b in zip(sent_faces, goz.faces) if not _rotation_equal(a, b) and _rotation_equal(a[::-1], b)
        )
        out["faces"] = {
            "identical": identical,
            "same_corners_rotated": rotated,
            "reversed_winding": reversed_,
            "other": len(sent_faces) - identical - rotated - reversed_,
        }
    same_order = same_counts and out["faces"]["identical"] == len(sent_faces)
    out["order"] = "same" if same_order else ("same counts, faces differ" if same_counts else "counts differ")
    if goz.points:
        mapping = axis_mapping(sent_points, goz.points, same_order)
        out["axes"] = mapping
        lo, hi = _bbox(sent_points)
        size = max(h - l for l, h in zip(lo, hi)) or 1.0
        # A candidate signed permutation (a sculpt of a few points skews the fit a little; the per-point check below is
        # exact). The tolerances only pick the candidate, they never count a point as unchanged.
        candidate = all(
            abs(abs(m["factor"]) - 1.0) < 1e-3 and abs(m["offset"]) < 1e-3 * size for m in mapping
        ) and len({m["from"] for m in mapping}) == 3
        out["mapping_is_signed_permutation"] = candidate
        if same_order and candidate:
            sign = {m["axis"]: (AXES.index(m["from"]), 1.0 if m["factor"] > 0 else -1.0) for m in mapping}
            changed, max_diff = [], 0.0
            for k, (expected, q) in enumerate(zip(sent_points, goz.points)):
                back = [0.0, 0.0, 0.0]
                for j, axis in enumerate(AXES):
                    i, s = sign[axis]
                    back[i] = s * q[j]  # a sign flip is exact in float32
                if back != list(expected):
                    changed.append(k)
                    max_diff = max(max_diff, max(abs(x - y) for x, y in zip(back, expected)))
            out["positions"] = {
                "bit_identical": len(sent_points) - len(changed),
                "changed": len(changed),
                "max_abs_diff": max_diff,
                "first_changed": changed[:10],
            }
    return out


def analysis_lines(result: dict) -> list[str]:
    lines = [f"Vergleich mit gesendetem Mesh {result['sent_id']}: Punkte/Flächen gesendet {result['counts']['sent']}, "
             f"empfangen {result['counts']['received']}"]
    if "axes" in result:
        terms = [
            f"{m['axis']}_goz = {m['factor']:+.6f}·{m['from']}_sent {m['offset']:+.6f}"
            + (f" (corr {m['corr']:+.6f})" if m["corr"] is not None else "")
            for m in result["axes"]
        ]
        method = result["axes"][0]["method"]
        lines.append(f"Achsen ({method}): " + ";  ".join(terms))
        scales = sorted({round(abs(m["factor"]), 6) for m in result["axes"]})
        lines.append(f"Maßstab: {scales}  (signed permutation, scale 1, offset 0: {result['mapping_is_signed_permutation']})")
    if "faces" in result:
        lines.append(f"Flächen: {result['faces']}")
    lines.append(f"Reihenfolge: {result['order']}")
    if "positions" in result:
        p = result["positions"]
        if p["changed"] == 0:
            lines.append("Rundreise unverändert: Punkte bitgleich (float32), Flächen gleich")
        else:
            lines.append(
                f"{p['changed']} Punkte geändert, {p['bit_identical']} bitgleich; max. Abweichung {p['max_abs_diff']:.6g}; "
                f"erste geänderte Indizes {p['first_changed']}"
            )
    return lines


def send_logs(captures: Path) -> list[dict]:
    logs = []
    for path in sorted(captures.glob("*/send_log.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        data["log_dir"] = str(path.parent)
        logs.append(data)
    return logs


def python_info() -> dict:
    return {"executable": sys.executable, "version": sys.version, "platform": sys.platform}
