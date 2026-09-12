"""Punch in (zoom + tilt) on the A-roll clips that start at the given frames and mark each in Cyan. See mr.edit.punch_in_clips."""
TIMELINE = "Raycast AI Update - Cut v1"; TRACK = 1; ZOOM = 1.3; TILT = -250.0
PUNCHES = [(898, "L04b pickup"), (3279, "L17 trimmed pause"), (7450, "L32b trimmed restart"), (7510, "")]
t = mr.find_timeline(project, TIMELINE)
result = mr.edit.punch_in_clips(resolve, project, t, PUNCHES, track=TRACK, zoom=ZOOM, tilt=TILT)
