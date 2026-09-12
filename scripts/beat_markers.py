"""Replace all markers on a timeline with one named, colored marker per beat. See mr.markers.beat_markers."""
TIMELINE = "GFX - Harness b-roll"; FPS = 24; NOTE = "beat"
BEATS = [(0.0, "A runtime", "Blue"), (1.8, "B window forms", "Cyan"), (3.4, "C ask", "Green"), (4.15, "D work", "Yellow"), (6.6, "E question", "Fuchsia"), (7.9, "F answer + resolve", "Purple"), (10.0, "hold", "Sky")]
t = mr.find_timeline(project, TIMELINE)
result = mr.markers.beat_markers(t, BEATS, fps=FPS, note=NOTE)
