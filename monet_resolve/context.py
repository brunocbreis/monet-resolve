"""Editorial context around a point in a cut, from local word-level transcripts.

The question this answers is the one Bruno asks while hand-editing: "what am I over, and what did the cut
drop around here?" Everything comes from the timeline items (source ranges) and the per-speaker word
files written at project start (`<spk>.words.json`: [[start_s, end_s, word], ...] in session seconds,
"(...)" for pauses). Resolve is read only for the playhead and the items; the words never leave disk.

Session seconds: a timeline item's source range maps to the call clock through `sources`,
{clip name or name fragment: {"offset": seconds at source frame 0, "fps": clip rate}}. For a multicam
whose Start TC is the session base (01:00:00:00 = session 0) the entry is {"offset": 0, "fps": 24}.
"""
import json
import os
from typing import Dict, List, Optional, Sequence, Tuple

from ._util import items, source_frames, tc_seconds, timeline_fps

PAUSE = "(...)"


def load_words(paths: Dict[str, str], base: str = "") -> List[List]:
    """Merge per-speaker word files into one list [[start, end, speaker, word], ...] sorted by start, pauses dropped."""
    out = []
    for spk, p in paths.items():
        with open(os.path.join(base, p), encoding="utf-8") as f:
            for w in json.load(f):
                if w[2] != PAUSE:
                    out.append([float(w[0]), float(w[1]), spk, str(w[2])])
    out.sort(key=lambda w: (w[0], w[2]))
    return out


def load_config(path: str) -> Dict:
    """Read an episode's `context.json` (timeline, words, names, sources) and resolve the word paths against its folder."""
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["_dir"] = os.path.dirname(os.path.abspath(path))
    cfg["_words"] = load_words(cfg["words"], cfg["_dir"])
    return cfg


def source_for(item, sources: Dict[str, Dict]) -> Optional[Dict]:
    """The `sources` entry whose key equals, or is contained in, the item's clip name."""
    clip = item.GetMediaPoolItem()
    if not clip:
        return None
    name = clip.GetName()
    if name in sources:
        return sources[name]
    for key, src in sources.items():
        if key in name:
            return src
    return None


def session_range(item, sources: Dict[str, Dict]) -> Optional[Tuple[float, float]]:
    """(start, end) of an item in session seconds, or None when its clip is not one of `sources`."""
    src = source_for(item, sources)
    if not src:
        return None
    a, b = source_frames(item)
    fps = float(src.get("fps", 24))
    off = float(src.get("offset", 0.0))
    return a / fps + off, b / fps + off


def text_between(words: Sequence[Sequence], t0: float, t1: float, names: Optional[Dict[str, str]] = None) -> str:
    """Words starting in [t0, t1), one line per speaker run: 'Hugo: ...'. Empty string when nothing is said."""
    names = names or {}
    lines, cur, buf = [], None, []
    for w in words:
        if w[0] < t0 or w[0] >= t1:
            continue
        if w[2] != cur:
            if buf:
                lines.append(f"{names.get(cur, cur)}: {' '.join(buf)}")
            cur, buf = w[2], []
        buf.append(w[3])
    if buf:
        lines.append(f"{names.get(cur, cur)}: {' '.join(buf)}")
    return "\n".join(lines)


def playhead_frame(timeline) -> int:
    """The playhead as a frame relative to the timeline start, from `GetCurrentTimecode()`."""
    fps = timeline_fps(timeline)
    return round(tc_seconds(timeline.GetCurrentTimecode(), fps) * fps) - timeline.GetStartFrame()


def cut_items(timeline, sources: Dict[str, Dict], track: int = 1) -> List[Dict]:
    """The dialogue items of video track `track`, in order, each with its timeline and session ranges.

    Items whose clip is not in `sources` (titles, graphics, b-roll) are left out, so the list reads as the
    spoken cut. Returns [{"item", "name", "start", "end", "session": (t0, t1)}] with frames relative.
    """
    s = timeline.GetStartFrame()
    out = []
    for x in sorted(items(timeline, "video", track), key=lambda i: i.GetStart()):
        rng = session_range(x, sources)
        if rng:
            out.append({"item": x, "name": x.GetName(), "start": x.GetStart() - s, "end": x.GetEnd() - s, "session": rng})
    return out


def marker_before(timeline, frame: int) -> Optional[Dict]:
    """The last marker at or before `frame` (relative): {"frame", "name", "note", "color"}."""
    best = None
    for f, m in timeline.GetMarkers().items():
        if f <= frame and (best is None or f > best["frame"]):
            best = {"frame": f, "name": m.get("name"), "note": m.get("note"), "color": m.get("color")}
    return best


def context_at(timeline, frame: int, words: Sequence[Sequence], sources: Dict[str, Dict],
               names: Optional[Dict[str, str]] = None, track: int = 1, tail: float = 12.0, lead: float = 12.0) -> Dict:
    """What is said at `frame` of the cut and what the cut dropped on both sides of it.

    Returns {"timeline", "frame", "chunk" (marker at or before), "this" or "gap", "before", "after"}:
    - "this": {"name", "start", "end", "session", "said" (the whole item's words), "here" (the ~6 s around
      the playhead)}; when the playhead sits in black, "gap": {"start", "end"} instead.
    - "before": {"prev" (name + its last `tail` seconds), "dropped" (seconds and words between the previous
      item's source end and this item's source start)}; the same shape for "after" with "next" and its first
      `lead` seconds. "dropped" is None when the two items are continuous in the call (under 0.5 s apart)
      and carries "reordered": True when the neighbour comes from a later/earlier point of the call.
    Judgement stays with the reader: this reports words, never delivery (worked 2026-10-22, wimr-hugo).
    """
    fps = timeline_fps(timeline)
    cut = cut_items(timeline, sources, track)
    k = next((i for i, c in enumerate(cut) if c["start"] <= frame < c["end"]), None)
    out = {"timeline": timeline.GetName(), "frame": frame, "chunk": marker_before(timeline, frame)}
    if k is None:
        prev_i = max([i for i, c in enumerate(cut) if c["end"] <= frame], default=None)
        nxt_i = min([i for i, c in enumerate(cut) if c["start"] > frame], default=None)
        out["gap"] = {"start": cut[prev_i]["end"] if prev_i is not None else 0,
                      "end": cut[nxt_i]["start"] if nxt_i is not None else None}
    else:
        c = cut[k]
        t0, t1 = c["session"]
        here = t0 + (frame - c["start"]) / fps
        out["this"] = {"name": c["name"], "start": c["start"], "end": c["end"], "session": [round(t0, 2), round(t1, 2)],
                       "said": text_between(words, t0, t1, names),
                       "here": text_between(words, max(t0, here - 3), min(t1, here + 3), names)}
        prev_i, nxt_i = k - 1 if k > 0 else None, k + 1 if k + 1 < len(cut) else None

    def side(neighbour, own_edge, is_before):
        if neighbour is None:
            return None
        n = cut[neighbour]
        n0, n1 = n["session"]
        own = own_edge
        if is_before:
            said = text_between(words, max(n0, n1 - tail), n1, names)
            gap0, gap1 = n1, own
        else:
            said = text_between(words, n0, min(n1, n0 + lead), names)
            gap0, gap1 = own, n0
        res = {("prev" if is_before else "next"): {"name": n["name"], "start": n["start"], "end": n["end"],
                                                  "session": [round(n0, 2), round(n1, 2)], "said": said}}
        if own is None:
            res["dropped"] = None
        elif gap1 - gap0 < 0.5:
            res["dropped"] = None if gap1 >= gap0 else {"reordered": True, "seconds": round(gap0 - gap1, 1)}
        else:
            res["dropped"] = {"seconds": round(gap1 - gap0, 1), "session": [round(gap0, 2), round(gap1, 2)],
                              "said": text_between(words, gap0, gap1, names)}
        return res

    this_t0 = out["this"]["session"][0] if "this" in out else None
    this_t1 = out["this"]["session"][1] if "this" in out else None
    out["before"] = side(prev_i, this_t0, True)
    out["after"] = side(nxt_i, this_t1, False)
    return out


def brief(ctx: Dict) -> str:
    """`context_at` as plain text for a reader (or a small model): what is said, what was dropped, no frame numbers."""
    L = []
    if ctx.get("chunk") and ctx["chunk"].get("name"):
        L.append(f"Chunk: {ctx['chunk']['name']}" + (f" - {ctx['chunk']['note']}" if ctx['chunk'].get('note') else ""))
    if "gap" in ctx:
        L.append("Playhead is in black between two clips.")
    else:
        t = ctx["this"]
        L.append(f"On clip: {t['name']}")
        L.append("Said in this clip:\n" + (t["said"] or "(nothing transcribed)"))
    for key, label in (("before", "Before it"), ("after", "After it")):
        s = ctx.get(key)
        if not s:
            continue
        nb = s.get("prev") or s.get("next")
        L.append(f"{label}: {nb['name']}\n" + (nb["said"] or "(nothing transcribed)"))
        d = s.get("dropped")
        if d is None:
            L.append("  -> continuous in the call, nothing dropped at this join.")
        elif d.get("reordered"):
            L.append("  -> this clip comes from a different point of the call (reordered).")
        else:
            L.append(f"  -> DROPPED {d['seconds']} s of the call here:\n{d['said'] or '(silence / untranscribed)'}")
    return "\n\n".join(L)


def cut_transcript(timeline, words: Sequence[Sequence], sources: Dict[str, Dict], names: Optional[Dict[str, str]] = None,
                   track: int = 1, max_dropped_chars: int = 600) -> str:
    """The whole cut as text: every dialogue item with its words, and between items what the cut dropped.

    Markdown, one `##` per item ("NN name · cut mm:ss · call mm:ss"), a quoted block for a dropped stretch
    (trimmed to `max_dropped_chars`, head and tail kept), chunk markers as `#` headings. Regenerate it after
    every pass on the cut and read it instead of asking Resolve what is where.
    """
    fps = timeline_fps(timeline)
    marks = sorted(timeline.GetMarkers().items())
    cut = cut_items(timeline, sources, track)
    L = [f"# {timeline.GetName()}", ""]
    mi = 0
    prev = None
    for n, c in enumerate(cut):
        while mi < len(marks) and marks[mi][0] <= c["start"]:
            m = marks[mi][1]
            L += [f"# {m.get('name')}" + (f"  \n_{m.get('note')}_" if m.get("note") else ""), ""]
            mi += 1
        t0, t1 = c["session"]
        if prev is not None:
            p1 = prev["session"][1]
            if t0 - p1 >= 0.5:
                dropped = text_between(words, p1, t0, names)
                if len(dropped) > max_dropped_chars:
                    h = max_dropped_chars // 2
                    dropped = dropped[:h] + " [...] " + dropped[-h:]
                L += [f"> dropped {t0 - p1:.0f} s of the call ({_mmss(p1)} - {_mmss(t0)}):", "> " + dropped.replace("\n", "\n> "), ""]
            elif t0 < p1 - 0.5:
                L += [f"> reordered: this clip comes from earlier in the call ({_mmss(t0)}).", ""]
        L += [f"## {n:02d} {c['name']} · cut {_mmss(c['start'] / fps)} · call {_mmss(t0)}-{_mmss(t1)}", "",
              text_between(words, t0, t1, names) or "(nothing transcribed)", ""]
        prev = c
    return "\n".join(L)


def _mmss(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"
