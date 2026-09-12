"""Add a vignette as a Fusion composition clip on a new top video track. See mr.titles.fusion_vignette_layer."""
TIMELINE = "Raycast AI Update - Cut v1"; TRACK_NAME = "GFX"; FPS = 24
CENTER = (0.5, 0.5); WIDTH = 1.0; HEIGHT = 1.0; SOFT = 0.25; OPACITY = 70.0
t = mr.find_timeline(project, TIMELINE)
result = mr.titles.fusion_vignette_layer(resolve, project, t, track_name=TRACK_NAME, center=CENTER, width=WIDTH, height=HEIGHT, soft=SOFT, opacity=OPACITY, fps=FPS)
