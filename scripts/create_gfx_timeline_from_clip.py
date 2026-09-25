"""Import a rendered GFX file, make a timeline from it, nest it on a cut track at a record frame. See mr.gfx.create_gfx_timeline_from_clip."""
PATH = "/path/to/project/teaser-broll/out/projects-4k-v1.mov"; GFX_BIN = "gfx"; TIMELINE_BIN = ["timelines", "gfx"]
GFX_TIMELINE = "GFX - Projects b-roll"; CUT = "Raycast AI Update - Cut v2"; TRACK = 3; RECORD = 1378; FRAMES = 303
mp = project.GetMediaPool()
cut = mr.find_timeline(project, CUT)
result = mr.gfx.create_gfx_timeline_from_clip(resolve, project, PATH, mr.find_bin(mp, GFX_BIN), mr.find_bin(mp, TIMELINE_BIN), GFX_TIMELINE, cut, TRACK, RECORD, FRAMES)
