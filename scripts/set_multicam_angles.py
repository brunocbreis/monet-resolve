"""Switch multicam items to angles through the menu bar. See mr.multicam.set_angles and mr.ui."""
TIMELINE = "Interview - Cut v1"; TRACK = 2; ANGLE = 4; START = 5400; END = 8700   # relative frames
t = mr.find_timeline(project, TIMELINE); s = t.GetStartFrame()
its = [x for x in t.GetItemListInTrack("video", TRACK) if START <= x.GetStart() - s < END]
result = mr.set_angles(resolve, project, t, [(x, ANGLE) for x in its])
