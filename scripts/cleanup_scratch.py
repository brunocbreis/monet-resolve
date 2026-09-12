"""Delete probe timelines, a scratch bin with its clips, and stray "Fusion Clip" pool items. Destructive. See mr.media.cleanup_scratch."""
TIMELINES = ["_probe"]; SCRATCH_BIN = "_scratch"; STRAY_PREFIX = "Fusion Clip"
result = mr.media.cleanup_scratch(resolve, project, timelines=TIMELINES, scratch_bin=SCRATCH_BIN, stray_prefix=STRAY_PREFIX, confirm=True)
