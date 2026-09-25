"""Close every timeline tab except the ones to keep (File > Close Timeline through the menu bar). See mr.ui."""
KEEP = ["Interview - Cut v2"]
resolve.OpenPage("edit"); closed = []
for t in mr.list_timelines(project):
    if t.GetName() in KEEP: continue
    project.SetCurrentTimeline(t)
    if mr.ui.close_current_timeline(): closed.append(t.GetName())
project.SetCurrentTimeline(mr.find_timeline(project, KEEP[0]))
result = {"closed": closed}
