"""Copy a Text title from another project with new words, wrap it in a Fusion clip, place it. See mr.richtext.
Needs `pip install zstandard`. Writes the project export and DRTs under WORKDIR."""
import os
SOURCE_PROJECT = "episode-01"; MATCH_TEXT = "Guest Name"; REPLACE = {"Guest Name": "New Guest", " Role at Company": " New role"}
TIMELINE = "Interview - Cut v1"; TRACK = 3; RECORD = 1000; FRAMES = 119; WORKDIR = "/tmp/richtext"; HELPER = "lower third (copied)"
os.makedirs(WORKDIR, exist_ok=True)
pm = resolve.GetProjectManager(); pm.SaveProject()
drp = os.path.join(WORKDIR, SOURCE_PROJECT + ".drp"); pm.ExportProject(SOURCE_PROJECT, drp, False)
gen = [g for g in mr.generators_in_drp(drp) if MATCH_TEXT in g["texts"]][0]
tpl = mr.make_template_drt(resolve, project, os.path.join(WORKDIR, "template.drt"))
drt = mr.title_drt(tpl, gen["xml"], os.path.join(WORKDIR, "title.drt"), HELPER, replace=REPLACE)
clip = mr.import_title_as_clip(resolve, project, drt, HELPER)
t = mr.find_timeline(project, TIMELINE); project.SetCurrentTimeline(t)
item = mr.append_exact(project.GetMediaPool(), t, clip, TRACK, RECORD, FRAMES, 0, exact=False)
result = {"source_texts": gen["texts"][:3], "placed": item.GetStart() - t.GetStartFrame() if item else None}
