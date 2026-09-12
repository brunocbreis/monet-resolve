"""Alternate wide and punched-in framing along the A-roll track; rewrite the Cyan PUNCH-IN markers. See mr.edit.alternate_punch_ins."""
TIMELINE = "Raycast AI Update - Cut v2"; TRACK = 1; ZOOM = 1.3; TILT = -250.0
t = mr.find_timeline(project, TIMELINE)
result = mr.edit.alternate_punch_ins(resolve, project, t, track=TRACK, zoom=ZOOM, tilt=TILT)
