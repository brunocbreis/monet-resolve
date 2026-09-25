"""Replace clips cut from source files with the synced multicam, then set each item's angle. See mr.multicam."""
TIMELINE = "Interview - Cut v1"; MULTICAM = "mcam - guest"; TRACKS = (1, 2)
SOURCES = {"guest-webcam.mp4": "Guest Webcam", "host-camera.MP4": "Host Cam", "guest-screen.mp4": "Screen"}   # file name -> angle name
t = mr.find_timeline(project, TIMELINE)
mcam = mr.find_clip(project.GetMediaPool().GetRootFolder(), MULTICAM)
mr.backup_timeline(resolve, project, t, TIMELINE + " - backup before multicam")
log = mr.swap_to_multicam(resolve, project, t, mcam, SOURCES, tracks=TRACKS)
numbers = mr.angle_numbers(SOURCES.values())
switched = mr.set_angles(resolve, project, t, [(r["item"], numbers[r["angle"]]) for r in log if "item" in r])
result = {"swapped": len([r for r in log if "item" in r]), "errors": [r for r in log if "error" in r], "angles": switched}
