"""Nest a timeline into the cut on a track, over a placeholder clip, sized to it. See mr.assembly.nest_timeline_over_placeholder."""
CUT = "Raycast AI Update - Cut v2"; NESTED = "GFX - Harness b-roll"; TIMELINE_BIN = ["timelines", "gfx"]
TRACK = 3; TRACK_NAME = "GFX nested"; PLACEHOLDER_START = 920; PLACEHOLDER_TRACK = 2
mp = project.GetMediaPool()
nested = mr.find_clip(mr.find_bin(mp, TIMELINE_BIN), NESTED, recursive=False)
cut = mr.find_timeline(project, CUT)
result = mr.assembly.nest_timeline_over_placeholder(resolve, project, cut, nested, TRACK, PLACEHOLDER_START, PLACEHOLDER_TRACK, track_name=TRACK_NAME, clear_track=True)
