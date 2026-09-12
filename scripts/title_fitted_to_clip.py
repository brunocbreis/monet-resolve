"""Insert a Text+ title on a track spanning exactly one clip's extent (found by name) and style it. See mr.titles.title_fitted_to_clip."""
TIMELINE = "Raycast AI Update - Cut v2"; OTHER = "Raycast AI Update - Selects (all takes)"
CLIP_TRACK = 1; CLIP_NAME = "L06b · Harness rewritten (T2, full)"; TRACK = 2
TEXT = "Harness"; FONT = "Inter 28pt"; STYLE = "Medium"; SIZE = 0.045; RGB = (1, 1, 1)
t = mr.find_timeline(project, TIMELINE); o = mr.find_timeline(project, OTHER)
result = mr.titles.title_fitted_to_clip(resolve, project, t, CLIP_TRACK, CLIP_NAME, TRACK, TEXT, other=o, font=FONT, style=STYLE, size=SIZE, rgb=RGB)
