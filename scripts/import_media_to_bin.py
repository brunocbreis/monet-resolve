"""Import files into a root bin (created when missing) and report each clip's properties. See mr.media.import_to_bin."""
BIN = "music"
PATHS = ["/Users/brunoreis/Work/raycast-ai-updates/music/" + n for n in ["Aves - Roasted.wav", "Danny Shields - Battery Bass.wav", "Out of Flux - What The Dog Doing.wav", "Ziggy - Walk the Walk.wav"]]
result = mr.media.import_to_bin(project.GetMediaPool(), PATHS, BIN)
