"""Copy Resolve Text titles (the Edit page "Text" generator, stored as PrettyType "Rich") between projects
and change their words, keeping font, size, position and styling exactly.

The API cannot read or set a Text title's content or style, cannot copy an item from one timeline to
another, and loading another project to look at it can crash Resolve. The route that works:

1. `pm.ExportProject(name, path)` writes the other project as a .drp without loading it (a zip of XML).
2. `generators_in_drp` finds each `Sm2TiGenerator` element: its `EffectFiltersBA` hex holds the title,
   a 9-byte header (00000002, big-endian length, 0x81) plus a zstd frame.
3. `replace_text` edits a string inside the decompressed data and fixes every length field around it.
4. `title_drt` puts the element into a DRT exported from a scratch timeline that holds one Text title;
   `MediaPool.ImportTimelineFromFile` brings it in as a timeline with that exact title.
5. `Timeline.CreateFusionClip([item])` makes a media pool item any timeline can `AppendToTimeline`.
   The result is a Fusion clip wrapping the Text title, so its words are edited by opening the clip.

Needs zstd: `pip install zstandard` (the `richtext` extra) or the `zstd` command line tool.
"""
import re
import subprocess
import zipfile
from typing import Dict, List, Optional

HEADER_MAGIC = bytes.fromhex("00000002")


def _zstd(data: bytes, compress: bool) -> bytes:
    """zstd through the `zstandard` module, or the `zstd` command line tool when the module is missing."""
    try:
        import zstandard
    except ImportError:
        try:
            return subprocess.run(["zstd", "-c" if compress else "-dc"], input=data, capture_output=True, check=True).stdout
        except FileNotFoundError as e:
            raise ImportError("richtext needs `pip install zstandard` or the zstd command") from e
    if compress:
        return zstandard.ZstdCompressor().compress(data)
    return zstandard.ZstdDecompressor().decompress(data, max_output_size=10 ** 7)


def decode_filters(hexblob: str) -> bytes:
    """EffectFiltersBA hex -> decompressed title data."""
    b = bytes.fromhex(hexblob)
    i = b.find(bytes.fromhex("28b52ffd"))          # zstd magic
    return _zstd(b[i:], compress=False)


def encode_filters(data: bytes) -> str:
    """Decompressed title data -> EffectFiltersBA hex, header rebuilt for the new length."""
    c = _zstd(bytes(data), compress=True)
    return (HEADER_MAGIC + (len(c) + 1).to_bytes(4, "big") + b"\x81" + c).hex()


def texts_in(data: bytes) -> List[str]:
    """The UTF-16 strings in title data that follow the (len+14, len+4) prefix pair: the visible text runs
    first, then font families and styles."""
    out, i = [], 0
    while i + 8 < len(data):
        outer = int.from_bytes(data[i:i + 4], "little"); inner = int.from_bytes(data[i + 4:i + 8], "little")
        n = inner - 4
        if 0 < n < 4000 and n % 2 == 0 and outer == inner + 10 and i + 8 + n <= len(data):
            try:
                s = data[i + 8:i + 8 + n].decode("utf-16-le")
                if s.isprintable():
                    out.append(s); i += 8 + n; continue
            except UnicodeDecodeError:
                pass
        i += 1
    return out


def _rvar(buf, i):
    n = sh = 0
    while True:
        b = buf[i]; n |= (b & 0x7F) << sh; i += 1; sh += 7
        if not b & 0x80:
            return n, i


def _wvar(n):
    o = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        if n:
            o.append(b | 0x80)
        else:
            o.append(b); return bytes(o)


def replace_text(data: bytes, old: str, new: str) -> bytes:
    """Replace one text run in title data and fix the lengths that enclose it.

    A run is UTF-16LE preceded by two little-endian uint32s (bytes + 14, bytes + 4). The first text
    block sits inside a chain of length fields: 0a <v> ... 4a <v> 08 0f 1a <v> 0a <v> 42 <v> <uint32>;
    each is adjusted by the size change. Raises ValueError when `old` is not a run or the chain does not
    match (a title layout not seen yet). Keeps every style attribute: fonts are per run, positions are
    elsewhere in the data.
    """
    d = bytearray(data)
    o, nw = old.encode("utf-16-le"), new.encode("utf-16-le")
    k = d.find(o)
    if k < 8 or int.from_bytes(d[k - 4:k], "little") != len(o) + 4 or int.from_bytes(d[k - 8:k - 4], "little") != len(o) + 14:
        raise ValueError(f"{old!r} is not a text run in this title")
    delta = len(nw) - len(o)
    d[k - 8:k] = (len(nw) + 14).to_bytes(4, "little") + (len(nw) + 4).to_bytes(4, "little")
    d[k:k + len(o)] = nw
    # walk the chain and rewrite its lengths
    if d[0] != 0x0A:
        raise ValueError("unexpected title layout (byte 0)")
    p = 1; L1, p = _rvar(d, p)
    j = d.find(b"\x4a", p + 6)                       # skip "08 30 18 00 38 00 4a 00"
    while d[j + 1] == 0x00:
        j = d.find(b"\x4a", j + 1)
    chain = []
    for tag in (0x4A, None, 0x1A, 0x0A, 0x42):
        if tag is None:                               # "08 0f"
            if d[j:j + 2] != b"\x08\x0f":
                raise ValueError("unexpected title layout (08 0f)")
            j += 2; continue
        if d[j] != tag:
            raise ValueError(f"unexpected title layout (tag {tag:#x})")
        v, e = _rvar(d, j + 1); chain.append((j + 1, e, v)); j = e
    u32 = int.from_bytes(d[j:j + 4], "little")
    if u32 != chain[-1][2]:
        raise ValueError("unexpected title layout (uint32)")
    d[j:j + 4] = (u32 + delta).to_bytes(4, "little")
    for a, e, v in reversed(chain):
        d[a:e] = _wvar(v + delta)
    v1s, v1e = 1, p
    d[v1s:v1e] = _wvar(L1 + delta + sum(len(_wvar(v + delta)) - (e - a) for a, e, v in chain))
    return bytes(d)


def generators_in_drp(drp_path: str) -> List[Dict]:
    """Every Sm2TiGenerator in a .drp/.drt: {"seq", "name", "pretty", "start", "duration", "xml", "texts"}.
    `start` is the record frame as stored (86400 = 01:00:00:00 at 24 fps)."""
    out = []
    with zipfile.ZipFile(drp_path) as z:
        for name in z.namelist():
            if not name.startswith("SeqContainer/"):
                continue
            x = z.read(name).decode("utf-8")
            for m in re.finditer(r'<Sm2TiGenerator DbId="[^"]*">.*?</Sm2TiGenerator>', x, re.S):
                g = m.group(0)
                h = re.search(r"<EffectFiltersBA>([0-9a-f]*)</EffectFiltersBA>", g)
                texts = []
                if h and h.group(1):
                    try:
                        texts = texts_in(decode_filters(h.group(1)))
                    except Exception:
                        texts = []
                out.append({"seq": name, "name": re.search(r"<Name>([^<]*)</Name>", g).group(1),
                            "pretty": (re.search(r"<PrettyType>([^<]*)</PrettyType>", g) or [None, ""])[1],
                            "start": int(re.search(r"<Start>(\d+)</Start>", g).group(1)),
                            "duration": int(re.search(r"<Duration>(\d+)</Duration>", g).group(1)),
                            "xml": g, "texts": texts})
    return out


def make_template_drt(resolve, project, path: str) -> str:
    """Export a scratch timeline holding one Text title as a DRT (the vessel for `title_drt`), then
    delete the scratch timeline. Returns `path`."""
    mp = project.GetMediaPool()
    cur = project.GetCurrentTimeline()
    t = mp.CreateEmptyTimeline("_richtext template")
    project.SetCurrentTimeline(t)
    resolve.OpenPage("edit")
    t.InsertTitleIntoTimeline("Text")
    t.Export(path, resolve.EXPORT_DRT)
    mp.DeleteTimelines([t])
    if cur:
        project.SetCurrentTimeline(cur)
    return path


def title_drt(template_drt: str, generator_xml: str, out_path: str, timeline_name: str,
              replace: Optional[Dict[str, str]] = None, start: int = 86400) -> str:
    """Write a DRT whose single timeline holds `generator_xml` (from `generators_in_drp`), with text
    runs replaced per `replace` ({old: new}). Returns `out_path`."""
    g = generator_xml
    h = re.search(r"<EffectFiltersBA>([0-9a-f]*)</EffectFiltersBA>", g).group(1)
    if replace:
        data = decode_filters(h)
        for a, b in replace.items():
            data = replace_text(data, a, b)
        g = g.replace(h, encode_filters(data))
    body = re.search(r'<Sm2TiGenerator DbId="[^"]*">(.*?)</Sm2TiGenerator>', g, re.S).group(1)
    body = re.sub(r"<Start>\d+</Start>", f"<Start>{start}</Start>", body)
    with zipfile.ZipFile(template_drt) as z:
        files = {n: z.read(n).decode("utf-8") for n in z.namelist()}
    old_name = re.search(r"<ProjectName>([^<]*)</ProjectName>", files.get("project.xml", ""))
    for n, x in files.items():
        if n.startswith("SeqContainer/"):
            x = re.sub(r'(<Sm2TiGenerator DbId="[^"]*">).*?(</Sm2TiGenerator>)', lambda m: m.group(1) + body + m.group(2), x, count=1, flags=re.S)
        if old_name:
            x = x.replace(old_name.group(1), timeline_name)
        files[n] = x
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, x in files.items():
            z.writestr(n, x)
    return out_path


def import_title_as_clip(resolve, project, drt_path: str, name: str, folder=None):
    """Import a title DRT as timeline `name` (in `folder`), wrap its title in a Fusion clip and return
    that media pool item, ready for `AppendToTimeline`. The helper timeline stays (it holds the source).
    Append with endFrame = duration (not duration - 1) to get the full length."""
    mp = project.GetMediaPool()
    if folder:
        mp.SetCurrentFolder(folder)
    t = mp.ImportTimelineFromFile(drt_path, {"timelineName": name})
    t.SetName(name)
    project.SetCurrentTimeline(t)
    resolve.OpenPage("edit")
    it = t.GetItemListInTrack("video", 1)[0]
    t.CreateFusionClip([it])
    return t.GetItemListInTrack("video", 1)[0].GetMediaPoolItem()
