"""Export graded frames of a timeline as PNG stills from the color page. See mr.color.export_stills."""
TIMELINE = "Raycast AI Update - Cut v1"; DIR = "/path/to/project/export/stills/"; FPS = 24
FRAMES = {"wide": 100, "punch": 3300, "outro": 7300}
t = mr.find_timeline(project, TIMELINE)
result = mr.color.export_stills(resolve, project, t, DIR, FRAMES, fps=FPS)
