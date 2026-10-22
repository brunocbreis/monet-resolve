"""What is being said under the playhead of the current timeline, and what the cut dropped around it.

Reads `<episode>/_edit/context.json` (EP env var = episode folder; default ~/Work/<project name>) for the
word files, speaker names and source clock mapping. Prints a plain-text brief; `result` holds the data.
See mr.context.context_at. Resolve is only read (playhead, items); nothing changes.
"""
import os
EP = os.environ.get("EP") or os.path.expanduser(f"~/Work/{project.GetName()}")
cfg = mr.context.load_config(os.path.join(EP, "_edit", "context.json"))
t = project.GetCurrentTimeline()
frame = mr.context.playhead_frame(t)
ctx = mr.context.context_at(t, frame, cfg["_words"], cfg["sources"], cfg.get("names"))
print(mr.context.brief(ctx))
result = ctx
