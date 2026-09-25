"""Point media pool clips at new files on disk; timelines using them follow. See mr.media.replace_clip_file."""
BIN = "gfx"; BASE = "/path/to/project/teaser-broll/out/"
REPLACEMENTS = {n + "-4k-v1.mov": BASE + n + "-4k-v2.mov" for n in ["automations", "projects", "providers"]}
result = mr.media.replace_clip_file(resolve, mr.find_bin(project.GetMediaPool(), BIN), REPLACEMENTS)
