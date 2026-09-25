"""Close every timeline tab except the ones to keep (File > Close Timeline through the menu bar). See mr.ui."""
KEEP = ["Interview - Cut v2"]
names = [project.GetTimelineByIndex(i).GetName() for i in range(1, project.GetTimelineCount() + 1)]
resolve.OpenPage("edit"); closed = []
for n in names:
    if n in KEEP: continue
    project.SetCurrentTimeline(mr.find_timeline(project, n))
    if mr.ui.close_current_timeline(): closed.append(n)
project.SetCurrentTimeline(mr.find_timeline(project, KEEP[0]))
result = {"closed": closed}
