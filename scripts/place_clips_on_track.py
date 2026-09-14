"""Append source ranges of one media pool clip onto a track at record frames, video only. See mr.assembly.place_clips_on_track.

Source frames are the clip's own (60p here); a 60p range lands int(n * 0.4) frames on a 24p timeline.
"""
CUT = "Raycast AI Update - Cut v3"; BIN = "screen-recs"; CLIP = "ai-settings.mp4"
TRACK = 4; TRACK_NAME = "SCREEN RECS"; ZOOM = 1.155; COLOR = "Cyan"
CLIPS = [  # (name, record start relative to the timeline, source in, source out)
    ("REC - AI Settings, Automations tab", 2051, 1638, 1926),
    ("REC - Automation examples list", 2312, 1980, 2168),
    ("REC - Account tab, credits + top up", 5521, 5130, 5914),
    ("REC - Account tab (tail)", 5834, 6230, 6315),
    ("REC - Models & Providers, connect", 5868, 2820, 3618),
    ("REC - External providers", 6383, 4080, 4580),
]
mp = project.GetMediaPool()
clip = mr.find_clip(mr.find_bin(mp, BIN), CLIP, recursive=False)
cut = mr.find_timeline(project, CUT)
result = mr.assembly.place_clips_on_track(resolve, project, cut, clip, TRACK, CLIPS, zoom=ZOOM, color=COLOR, track_name=TRACK_NAME)
