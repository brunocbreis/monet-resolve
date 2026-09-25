"""Editorial QC for assembly cuts built from transcripts: edge placement, rule checks, a paper edit.

This is the gate a cut passes before delivery. It works on the cut *plan* (the list of
segments `assembly.build_synced_cut` takes), the word timings of every source clock and audio
envelopes of the dialogue tracks, so it runs in seconds and needs no render.

Needs numpy (run it with a Python that has numpy; the Resolve runner's system Python may not).

Segment dict keys used here: "a", "b" (seconds on the segment's clock), "video" (source key),
"audio" ([(key, track)]), "props", "overlays", "gap", "name", optional "allow_short" (a deliberate
short beat) and "reviewed" (a REVIEW finding was read and accepted, with a reason string).

Rules and thresholds live in RULES so they can be tuned per project. Severity: FAIL blocks delivery,
WARN must be fixed or justified in the notes, REVIEW means a human-style read is required.

`solo_env` (check_cut, fix_edges) maps an audio source key to the index of its envelope in
`envs[clock]`: a segment whose audio all comes from that one source is checked against that envelope
alone, so the other speaker's mic does not flag its edges.
"""
import re
import wave
from typing import Dict, List, Optional, Sequence

RULES = {
    "fragment_min_s": 2.5,          # a standalone shot shorter than this reads as a blip
    "slice_db": -35.0,              # speech-level audio at a hard edge means a word is being cut
    "slice_window_s": 0.03,
    "silence_db": -45.0,            # below this counts as air
    "min_air_out_s": 0.20,          # air kept after the last word before a hard cut
    "min_air_in_s": 0.10,           # air kept before the first word after a hard cut
    "static_shot_s": 40.0,          # longest stretch with no picture change (cut or overlay)
    "faceless_s": 60.0,             # longest stretch of screen recording with no face on screen
    "context_jump_s": 30.0,         # a reply taken from this far away in the source must be read in context
    "lead": 0.25,                   # edge placement: air before the first word
    "tail": 0.45,                   # edge placement: air after the last word
}
NOISE = {"]", "sound", "effect", "effect]"}


# ---------------------------------------------------------------- audio and words

def load_envelope(path: str, offset: float = 0.0, rate: int = 100) -> Dict:
    """RMS envelope (dBFS, `rate` values per second) of a 16-bit wav, mixed to mono.

    `offset` is the clock time of the file's first sample (a StreamYard track starting 0.493 s into
    the session has offset 0.493), so `level(env, t)` takes clock time.
    """
    import numpy as np
    with wave.open(path) as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)
    h = sr // rate
    m = len(x) // h
    e = 20 * np.log10(np.sqrt((x[: m * h].reshape(m, h) ** 2).mean(1)) + 1e-7)
    return {"e": e, "off": offset, "rate": rate}


def level(envs: Sequence[Dict], t: float) -> float:
    """Loudest level across `envs` at clock time `t` (dBFS); -120 outside every file."""
    v = -120.0
    for E in envs:
        i = int(round((t - E["off"]) * E["rate"]))
        if 0 <= i < len(E["e"]):
            v = max(v, float(E["e"][i]))
    return v


def clean_words(words: Sequence[Sequence]) -> List[List]:
    """Drop transcript tokens that are not speech: '(Silence)', '(Laugh)', 'Sound effect ]'."""
    return [list(w) for w in words if not str(w[3]).startswith("(") and str(w[3]).strip().lower() not in NOISE
            and not str(w[3]).endswith("]")]


def place_edges(words: Sequence[Sequence], envs: Sequence[Dict], speaker: str, t0: float, t1: float,
                rules: Dict = RULES) -> Dict:
    """Cut points for one speaker's passage from word `t0` to word `t1`, with air on both sides.

    `words` are [start, end, speaker, text] on one clock. The passage is the speaker's words starting
    at/after t0 and starting at/before t1. The in point is `lead` before the first word and the out
    point `tail` after the last, pulled in so no neighbouring word (either speaker) is included, then
    moved to the quietest 10 ms within 80 ms when the envelope shows speech there. Transcript word
    times drift by 100-150 ms; the envelope decides. Returns {"a", "b", "text", "first", "last"}.
    """
    ws = [w for w in words if w[2] == speaker and w[0] >= t0 - 0.06 and w[0] <= t1]
    if not ws:
        raise ValueError(f"no words for {speaker} between {t0} and {t1}")
    a_w, b_w = ws[0][0], ws[-1][1]
    others = [w for w in words if w not in ws]
    prev_end = max([w[1] for w in others if w[1] < a_w - 0.01] or [a_w - 5])
    next_start = min([w[0] for w in others if w[0] > ws[-1][0] + 0.01] or [b_w + 5])
    a = max(a_w - rules["lead"], prev_end + 0.06)
    b = min(b_w + rules["tail"], next_start - 0.06)
    a = _quietest(envs, a, 0.08, rules["silence_db"])
    b = _quietest(envs, b, 0.08, rules["silence_db"])
    return {"a": round(a, 3), "b": round(b, 3), "text": " ".join(str(w[3]) for w in ws),
            "first": ws[0][3], "last": ws[-1][3]}


def _quietest(envs, t, radius, silence_db):
    if level(envs, t) <= silence_db:
        return t
    best, bt = 1e9, t
    k = -radius
    while k <= radius + 1e-9:
        v = level(envs, t + k)
        if v < best:
            best, bt = v, t + k
        k += 0.01
    return bt


# ---------------------------------------------------------------- the rule set

def _continuous(segments, clock_of, i, j) -> bool:
    """Segment j continues segment i on the same clock with no gap (a through-edit, not a hard cut)."""
    return (0 <= i < len(segments) and 0 <= j < len(segments) and not segments[i].get("gap")
            and clock_of.get(segments[i]["video"], "session") == clock_of.get(segments[j]["video"], "session")
            and abs(segments[i]["b"] - segments[j]["a"]) < 0.02)


def _segment_envs(s, envs, clock, solo_env):
    """The dialogue envelopes that matter for segment `s` (see `solo_env` in the module docstring)."""
    E = envs.get(clock, [])
    keys = {k for k, _ in s["audio"]}
    if solo_env and len(keys) == 1 and next(iter(keys)) in solo_env:
        i = solo_env[next(iter(keys))]
        return E[i:i + 1]
    return E


def check_cut(segments: Sequence[Dict], words: Dict[str, List], envs: Dict[str, List[Dict]],
              clock_of: Dict[str, str], speaker_of: Dict[str, str], screen_keys: Sequence[str] = (),
              target_s: Optional[Sequence[float]] = None, rules: Dict = RULES, fps: float = 24.0,
              solo_env: Optional[Dict[str, int]] = None) -> List[Dict]:
    """Run every rule over a cut plan. Returns findings sorted by position in the cut.

    `words[clock]` and `envs[clock]` hold the word list and dialogue envelopes per clock ("session",
    "intro", "outro"); `clock_of[video_key]` names the clock a segment's range is on (default
    "session"); `speaker_of[video_key]` says whose face that angle shows (None for a screen).
    Each finding: {"severity", "rule", "seg", "at" (seconds into the cut), "detail"}.
    """
    out: List[Dict] = []
    pos, starts = 0.0, []
    for s in segments:
        starts.append(pos)
        pos += round((s["b"] - s["a"]) * fps) / fps + s.get("gap", 0) / fps
    total = pos

    def add(sev, rule, i, at, detail):
        out.append({"severity": sev, "rule": rule, "seg": i, "at": round(at, 2), "detail": detail})

    def cont(i, j):
        return _continuous(segments, clock_of, i, j)

    for i, s in enumerate(segments):
        ck = clock_of.get(s["video"], "session")
        W, E = words.get(ck, []), _segment_envs(s, envs, ck, solo_env)
        ws = [w for w in W if s["a"] <= (w[0] + w[1]) / 2 < s["b"]]
        txt = " ".join(str(w[3]) for w in ws)
        dur = s["b"] - s["a"]
        cin, cout = cont(i - 1, i), cont(i, i + 1)
        # FRAGMENT
        if dur < rules["fragment_min_s"] and not s.get("allow_short") and not (cin or cout):
            add("FAIL", "FRAGMENT", i, starts[i], f"{dur:.1f}s standalone shot: '{txt}'")
        # WORD_SLICE and AIR at hard edges
        for edge, is_cont, name in ((s["a"], cin, "in"), (s["b"], cout, "out")):
            if is_cont or not E:
                continue
            k, lv = -rules["slice_window_s"], -120.0
            while k <= rules["slice_window_s"] + 1e-9:
                lv = max(lv, level(E, edge + k))
                k += 0.01
            if lv > rules["slice_db"]:
                add("FAIL", "WORD_SLICE", i, starts[i] + (0 if name == "in" else dur),
                    f"{name} edge at {edge:.2f} sits in speech ({lv:.0f} dBFS): '{txt[:40] if name == 'in' else txt[-40:]}'")
            else:
                air, step = 0.0, (0.01 if name == "in" else -0.01)
                t = edge
                while abs(air) < 1.0 and level(E, t) <= rules["silence_db"]:
                    t += step
                    air += 0.01
                need = rules["min_air_in_s"] if name == "in" else rules["min_air_out_s"]
                if air < need:
                    add("WARN", "NO_AIR", i, starts[i] + (0 if name == "in" else dur),
                        f"{name} edge keeps {air:.2f}s of air (want {need:.2f}s)")
        # DANGLING text
        if ws and not (cin or cout) and s["video"] not in screen_keys:
            if not re.search(r"[.?!]$", str(ws[-1][3])):
                add("WARN", "ENDS_MID_SENTENCE", i, starts[i] + dur, f"ends on '{ws[-1][3]}'")
            if re.match(r"^[a-z]", str(ws[0][3])) and ws[0][3] not in ("i",):
                add("WARN", "STARTS_MID_SENTENCE", i, starts[i], f"starts on '{ws[0][3]}'")
        # angle and context rules against the previous segment
        if i > 0:
            p = segments[i - 1]
            same_look = p["video"] == s["video"] and (p.get("props") or {}) == (s.get("props") or {})
            covered = any(abs((o.get("at", o["a"]) - s["a"])) < 0.5 or (o.get("at", o["a"]) < s["a"] < o.get("at", o["a"]) + (o["b"] - o["a"]))
                          for o in (s.get("overlays") or []) + (p.get("overlays") or []))
            if same_look and not cin and not covered and s["video"] not in screen_keys and not p.get("gap"):
                add("FAIL", "JUMP_CUT", i, starts[i], f"'{s['video']}' to itself with the same framing and nothing covering the join")
            if cin and p["video"] != s["video"]:
                away = speaker_of.get(p["video"])
                inside = [w for w in W if w[2] == away and w[0] + 0.05 < s["a"] < w[1] - 0.05]
                if inside:
                    add("WARN", "MID_WORD_SWITCH", i, starts[i], f"angle leaves {away} inside '{inside[0][3]}'")
            ps, ss = speaker_of.get(p["video"]), speaker_of.get(s["video"])
            if ck == clock_of.get(p["video"], "session") and ps and ss and ps != ss and abs(s["a"] - p["b"]) > rules["context_jump_s"]:
                if not s.get("reviewed"):
                    add("REVIEW", "CONTEXT_JUMP", i, starts[i], f"{ss} replies with a line from {abs(s['a'] - p['b']):.0f}s away: '{txt[:60]}'")
    # STATIC_SHOT and FACELESS over the whole cut
    changes = sorted(set([0.0] + starts + [starts[i] + (o.get("at", o["a"]) - s["a"]) + d
                                          for i, s in enumerate(segments) for o in (s.get("overlays") or [])
                                          for d in (0.0, o["b"] - o["a"])] + [total]))
    for x, y in zip(changes, changes[1:]):
        if y - x > rules["static_shot_s"]:
            add("WARN", "STATIC_SHOT", -1, x, f"{y - x:.0f}s with no picture change")
    run, run_start = 0.0, 0.0
    for i, s in enumerate(segments):
        face_overlay = any(speaker_of.get(o["src"]) for o in (s.get("overlays") or []))
        if s["video"] in screen_keys and not face_overlay:
            if run == 0:
                run_start = starts[i]
            run += s["b"] - s["a"]
            if run > rules["faceless_s"]:
                add("WARN", "FACELESS", i, run_start, f"{run:.0f}s of screen with no face")
                run = -1e9
        else:
            run = 0.0
    if target_s and not (target_s[0] <= total <= target_s[1]):
        add("WARN", "LENGTH", -1, total, f"{total / 60:.2f} min outside {target_s[0] / 60:.1f}-{target_s[1] / 60:.1f}")
    return sorted(out, key=lambda f: f["at"])


def paper_edit(segments: Sequence[Dict], words: Dict[str, List], clock_of: Dict[str, str],
               speaker_of: Dict[str, str], fps: float = 24.0) -> str:
    """The cut as a script: one line per segment, cut time, angle, and every word heard (both tracks).

    Read it top to bottom as a viewer before delivery: each line must follow from the one before,
    no reaction may answer something that was cut, no sentence may start or stop mid-thought.
    """
    lines, pos = [], 0.0
    for i, s in enumerate(segments):
        ck = clock_of.get(s["video"], "session")
        ws = [w for w in words.get(ck, []) if s["a"] <= (w[0] + w[1]) / 2 < s["b"]]
        heard = " ".join(f"{w[2][:1]}:{w[3]}" if j == 0 or ws[j - 1][2] != w[2] else str(w[3]) for j, w in enumerate(ws))
        ov = " +B-ROLL" if s.get("overlays") else ""
        lines.append(f"{i:02d} {int(pos // 60)}:{pos % 60:05.2f} [{s['video']}{ov}] {heard}")
        pos += round((s["b"] - s["a"]) * fps) / fps + s.get("gap", 0) / fps
        if s.get("gap"):
            lines.append(f"   {int(pos // 60)}:{pos % 60:05.2f} -- {s['gap'] / fps:.1f}s slot (title / card) --")
    return "\n".join(lines)


def report(findings: Sequence[Dict]) -> str:
    """Findings as a table, FAILs first. The gate: zero FAIL, every WARN fixed or justified, every REVIEW read."""
    order = {"FAIL": 0, "WARN": 1, "REVIEW": 2}
    rows = sorted(findings, key=lambda f: (order[f["severity"]], f["at"]))
    head = f"{sum(f['severity'] == 'FAIL' for f in rows)} FAIL, {sum(f['severity'] == 'WARN' for f in rows)} WARN, {sum(f['severity'] == 'REVIEW' for f in rows)} REVIEW"
    return head + "\n" + "\n".join(f"{f['severity']:6s} {f['rule']:20s} seg {f['seg']:>3} @ {int(f['at'] // 60)}:{f['at'] % 60:05.2f}  {f['detail']}" for f in rows)


def fix_edges(segments: List[Dict], words: Dict[str, List], envs: Dict[str, List[Dict]], clock_of: Dict[str, str],
              quiet_db: float = -42.0, reach: float = 0.4, rules: Dict = RULES,
              solo_env: Optional[Dict[str, int]] = None) -> List[str]:
    """Move every hard edge that sits in speech to the nearest quiet point on all dialogue tracks.

    An in edge may move earlier (up to `reach`) or later but never past the segment's first own word;
    an out edge may move later (up to `reach`) or earlier but never before its last own word. Edges
    shared by continuous segments are left alone. Mutates `segments`; returns a log line per edge,
    including edges it could not fix (those need a different cut point chosen by hand).
    """
    log = []
    for i, s in enumerate(segments):
        ck = clock_of.get(s["video"], "session")
        E = _segment_envs(s, envs, ck, solo_env)
        if not E:
            continue
        own = [w for w in words.get(ck, []) if s["a"] <= (w[0] + w[1]) / 2 < s["b"]]
        for name in ("a", "b"):
            if (name == "a" and _continuous(segments, clock_of, i - 1, i)) or (name == "b" and _continuous(segments, clock_of, i, i + 1)):
                continue
            edge = s[name]
            peak = max(level(E, edge + k * 0.01) for k in range(-3, 4))
            if peak <= rules["slice_db"]:
                continue
            lo, hi = edge - reach, edge + reach
            if own and name == "a":
                hi = min(hi, own[0][0] - 0.02)
            if own and name == "b":
                lo = max(lo, own[-1][1] - 0.05)
            cands = []
            t = lo
            while t <= hi:
                if max(level(E, t + k * 0.01) for k in range(-2, 3)) <= quiet_db:
                    cands.append(t)
                t += 0.01
            if cands:
                new = min(cands, key=lambda x: abs(x - edge))
                s[name] = round(new, 3)
                log.append(f"seg {i} {name}: {edge:.2f} -> {new:.2f}")
            else:
                log.append(f"seg {i} {name}: {edge:.2f} UNFIXED (no quiet point within {reach}s)")
    return log


BACKCHANNEL = {"yeah", "yes", "yep", "okay", "ok", "mm", "hmm", "mm-hmm", "uh-huh", "right", "wow", "cool", "sure",
               "nice", "exactly", "oh", "ah", "alright"}


def silent_audio_items(items: Sequence[Dict], words: Sequence[Sequence], sources: Dict[str, Dict]) -> List[Dict]:
    """Audio items that should be muted: the track's speaker says nothing but backchannels inside the item.

    `items` are {"track", "start", "clip", "fps", "si", "so"} read from the timeline (GetSourceStartFrame/
    GetSourceEndFrame); `sources[clip_name]` = {"offset": session seconds at frame 0, "speaker": name, or
    None for a non-dialogue source with "keep_from"/"keep_to" session seconds where its sound is wanted}.
    Rule behind it: only what is meant to be heard stays enabled; a second mic under an answer adds room
    tone and "yeah"s, and a screen recording's audio plays only where its sound is the point.
    Returns the items to disable with a "why".
    """
    out = []
    for it in items:
        src = sources.get(it["clip"])
        if not src:
            continue
        a = it["si"] / it["fps"] + src["offset"]
        b = it["so"] / it["fps"] + src["offset"]
        if src.get("speaker") is None:
            if not (src.get("keep_from", -1e9) <= a and b <= src.get("keep_to", 1e9)):
                out.append({**it, "why": f"non-dialogue audio outside its wanted range ({a:.0f}-{b:.0f}s)"})
            continue
        ws = [w for w in words if w[2] == src["speaker"] and a <= (w[0] + w[1]) / 2 < b]
        if not [w for w in ws if re.sub(r"[^a-z\-']", "", str(w[3]).lower()) not in BACKCHANNEL]:
            out.append({**it, "why": f"{src['speaker']} silent or backchannel only ({' '.join(str(w[3]) for w in ws)[:30]})"})
    return out
