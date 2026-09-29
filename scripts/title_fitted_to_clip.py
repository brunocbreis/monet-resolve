"""Insert a Text+ title on a track spanning exactly one clip's extent (found by name). See mr.titles.title_fitted_to_clip."""
TIMELINE = "Cut v2"; OTHER = "Selects"
CLIP_TRACK = 1; CLIP_NAME = "Interview answer"; TRACK = 2; TEXT = "Answer"
t = mr.find_timeline(project, TIMELINE); o = mr.find_timeline(project, OTHER)
result = mr.title_fitted_to_clip(resolve, project, t, CLIP_TRACK, CLIP_NAME, TRACK, text=TEXT, other=o)
