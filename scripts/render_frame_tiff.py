"""Render single frames of a timeline as TIFF files, one job per frame, and wait. Clears the render queue. See mr.render.render_frame_tiff."""
TIMELINE = "Raycast AI Update - Cut v2"; DIR = "/path/to/project/export/frames/"; TIMEOUT = 80
FRAMES = {"wide": 100, "punch": 3300}
t = mr.find_timeline(project, TIMELINE)
result = mr.render.render_frame_tiff(project, t, DIR, FRAMES, timeout=TIMEOUT)
