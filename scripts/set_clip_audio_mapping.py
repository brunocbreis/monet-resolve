"""Set a clip's audio track mapping so appends land the right channels on the right tracks. See mr.audio.set_clip_audio_mapping."""
BIN = "footage"; CLIP = None
MAPPING = {"1": {"channel_idx": [3], "mute": False, "type": "mono"}, "2": {"channel_idx": [1, 2], "mute": False, "type": "stereo"}}
c = mr.find_clip(mr.find_bin(project.GetMediaPool(), BIN), CLIP, recursive=False)
result = mr.set_clip_audio_mapping(c, MAPPING)
mr.save(resolve)
