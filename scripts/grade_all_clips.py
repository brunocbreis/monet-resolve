"""Apply a DRX node tree to every clip on a track that lacks it, then set CDL values on chosen nodes. See mr.color.grade_all_clips."""
TIMELINE = "Raycast AI Update - Cut v2"; TRACK = 1; DRX = "/path/to/color_1.43.1.drx"; NODES = 7
CDLS = [{"NodeIndex": 1, "Slope": "0.69 0.69 0.69", "Offset": "0 0 0", "Power": "1 1 1", "Saturation": 1.0},
        {"NodeIndex": 3, "Slope": "1.35 1.35 1.35", "Offset": "0 0 0", "Power": "1.25 1.25 1.25", "Saturation": 1.10}]
t = mr.find_timeline(project, TIMELINE)
result = mr.color.grade_all_clips(resolve, project, t, DRX, NODES, CDLS, track=TRACK)
