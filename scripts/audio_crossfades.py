"""Add a short audio crossfade between every pair of touching clips on one audio track. See mr.audio.audio_crossfades."""
TIMELINE = "Raycast AI Update - Cut v2"; TRACK = 1; FRAMES = 4; TYPE = "Cross Fade +3 dB"
t = mr.find_timeline(project, TIMELINE)
result = mr.audio.audio_crossfades(resolve, project, t, track=TRACK, frames=FRAMES, transition_type=TYPE)
