"""The checked testbed project, frozen: freeze it once it looks right, verify it before every run, restore it.

    python3 -m testbed.baseline freeze    # export monet-testbed.drp and fingerprint the base timelines
    python3 -m testbed.baseline verify    # compare the open project's base timelines to the fingerprint
    python3 -m testbed.baseline restore   # replace the monet-testbed project with the frozen .drp

The fingerprint is a hash of each base timeline's DRT export with Resolve's per-export IDs and timestamps
taken out, so two exports of an unchanged timeline hash the same. Everything lives in testbed/baseline/,
which git ignores; build.py stays the recipe to recreate it.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile

import monet_resolve as mr

from .build import PROJECT

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "baseline")
DRP = os.path.join(DIR, PROJECT + ".drp")
FINGERPRINT = os.path.join(DIR, "fingerprint.json")
UUID = rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
ZSTD_MAGIC = bytes.fromhex("28b52ffd")


def _unzstd(data: bytes) -> bytes:
    try:
        import zstandard
        return zstandard.ZstdDecompressor().decompress(data, max_output_size=10 ** 8)
    except ImportError:
        return subprocess.run(["zstd", "-d", "-c"], input=data, capture_output=True, check=True).stdout


def _canonical_blob(hexblob: str) -> str:
    raw = bytes.fromhex(hexblob)
    i = raw.find(ZSTD_MAGIC)
    data = _unzstd(raw[i:]) if i >= 0 else raw
    return re.sub(UUID, b"UUID", data.replace(b"\x00", b"")).hex()


def canonical_timeline(resolve, timeline) -> str:
    """The timeline's DRT export as text, with per-export IDs and timestamps replaced by placeholders."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "t.drt")
        if not timeline.Export(path, resolve.EXPORT_DRT):
            raise RuntimeError(f"could not export {timeline.GetName()!r}")
        with zipfile.ZipFile(path) as z:
            xml = "".join(z.read(n).decode("utf-8") for n in sorted(z.namelist()) if n.startswith("SeqContainer/"))
    xml = re.sub(r"<(\w+)>([0-9a-f]{16,})</\1>", lambda m: f"<{m.group(1)}>{_canonical_blob(m.group(2))}</{m.group(1)}>", xml)
    return re.sub(UUID.decode(), "UUID", xml)


def fingerprint(resolve, project) -> dict:
    base = mr.find_bin(project.GetMediaPool(), ["timelines", "base"])
    names = sorted(c.GetName() for c in base.GetClipList())
    return {n: hashlib.sha256(canonical_timeline(resolve, mr.find_timeline(project, n)).encode()).hexdigest() for n in names}


def freeze() -> dict:
    resolve, project = mr.connect()
    if project.GetName() != PROJECT:
        raise SystemExit(f"open {PROJECT!r} first")
    os.makedirs(DIR, exist_ok=True)
    mr.save(resolve)
    fp = fingerprint(resolve, project)
    if not resolve.GetProjectManager().ExportProject(PROJECT, DRP, False):
        raise SystemExit("ExportProject failed")
    with open(FINGERPRINT, "w") as fh:
        json.dump(fp, fh, indent=1)
    return {"drp": DRP, "fingerprint": fp}


def verify(resolve=None, project=None) -> list:
    """Base timelines whose fingerprint differs from the frozen one (empty when the baseline is intact)."""
    if resolve is None:
        resolve, project = mr.connect()
    if not os.path.exists(FINGERPRINT):
        raise SystemExit("no frozen baseline yet: build, check it in Resolve, then `python3 -m testbed.baseline freeze`")
    with open(FINGERPRINT) as fh:
        want = json.load(fh)
    have = fingerprint(resolve, project)
    return sorted(n for n in set(want) | set(have) if want.get(n) != have.get(n))


def restore() -> str:
    """Delete the monet-testbed project and import the frozen .drp in its place."""
    if not os.path.exists(DRP):
        raise SystemExit("no frozen .drp yet")
    resolve, _ = mr.connect(require_project=False)
    pm = resolve.GetProjectManager()
    cur = pm.GetCurrentProject()
    if cur and cur.GetName() == PROJECT:
        pm.CloseProject(cur)
    if PROJECT in (pm.GetProjectListInCurrentFolder() or []) and not pm.DeleteProject(PROJECT):
        raise SystemExit(f"could not delete {PROJECT!r}")
    if not pm.ImportProject(DRP, PROJECT):
        raise SystemExit("ImportProject failed")
    pm.LoadProject(PROJECT)
    return PROJECT


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    out = {"freeze": freeze, "verify": verify, "restore": restore}[cmd]()
    print(json.dumps(out, indent=1))
