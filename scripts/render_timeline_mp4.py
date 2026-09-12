"""Render a whole timeline to H.264 MP4 at a given size and poll the job. Clears the render queue. See mr.render.render_timeline_mp4."""
TIMELINE = "Raycast AI Update - Cut v2"; DIR = "/Users/brunoreis/Work/raycast-ai-updates/export"; NAME = "Raycast AI Update - Cut v2 review 1080p v2"
WIDTH = 1920; HEIGHT = 1080; WAIT = 55
t = mr.find_timeline(project, TIMELINE)
result = mr.render.render_timeline_mp4(resolve, project, t, DIR, NAME, width=WIDTH, height=HEIGHT, wait=WAIT)
