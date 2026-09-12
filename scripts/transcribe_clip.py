"""Transcribe a media pool clip with Resolve's speech-to-text; return segment lines or word timings. See mr.transcription.transcribe_clip."""
BIN = "footage"; CLIP = None; WORDS = False
c = mr.find_clip(mr.find_bin(project.GetMediaPool(), BIN), CLIP, recursive=False)
result = mr.transcription.transcribe_clip(c, words=WORDS)
