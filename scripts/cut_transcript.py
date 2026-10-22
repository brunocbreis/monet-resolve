"""Write the current cut as a text transcript (every clip's words plus what was dropped between clips).

Reads `<episode>/_edit/context.json` (EP env var = episode folder; default ~/Work/<project name>), uses the
timeline named there (or the current one when TIMELINE=current), writes `<episode>/_edit/cut.transcript.md`.
See mr.context.cut_transcript. Re-run after every pass on the cut.
"""
import os
EP = os.environ.get("EP") or os.path.expanduser(f"~/Work/{project.GetName()}")
cfg = mr.context.load_config(os.path.join(EP, "_edit", "context.json"))
name = os.environ.get("TIMELINE") or cfg.get("timeline")
t = project.GetCurrentTimeline() if name in (None, "current") else mr.find_timeline(project, name)
text = mr.context.cut_transcript(t, cfg["_words"], cfg["sources"], cfg.get("names"))
out = os.path.join(EP, "_edit", "cut.transcript.md")
with open(out, "w", encoding="utf-8") as f:
    f.write(text)
result = {"timeline": t.GetName(), "file": out, "clips": text.count("\n## "), "dropped_blocks": text.count("> dropped ")}
