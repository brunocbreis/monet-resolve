"""Set a clip's audio track mapping so appends land on the right tracks; optionally remap a timeline's A1 items. See mr.audio."""
BIN = "footage"; CLIP = None; TIMELINE = None
MAPPING = {"1": {"channel_idx": [3], "mute": False, "type": "mono"}, "2": {"channel_idx": [1, 2], "mute": False, "type": "stereo"}}
c = mr.find_clip(mr.find_bin(project.GetMediaPool(), BIN), CLIP, recursive=False)
result = mr.audio.set_clip_audio_mapping(c, MAPPING)
if TIMELINE:
    result["items_remapped"] = mr.audio.remap_timeline_audio_items(project, mr.find_timeline(project, TIMELINE), MAPPING)
mr.save(resolve)
