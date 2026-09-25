"""Project-level calls: load a project by name, map a project."""
from typing import Dict, Optional, Tuple

from ._util import find_timeline, list_timelines
from .media import list_bins
from .timelines import map_timeline


def load_project(resolve, name: str) -> Tuple[object, Dict]:
    """Load the project named `name` when it is not the current one; return (Project, info).

    `info` has the project name, its timeline names, the current timeline name, the project frame rate
    and resolution. After `LoadProject` any previously held Project object is stale: use the returned one.
    """
    pm = resolve.GetProjectManager()
    p = pm.GetCurrentProject()
    if not p or p.GetName() != name:
        p = pm.LoadProject(name)
    cur = p.GetCurrentTimeline()
    info = {
        "project": p.GetName(),
        "timelines": [t.GetName() for t in list_timelines(p)],
        "current": cur.GetName() if cur else None,
        "fps": p.GetSetting("timelineFrameRate"),
        "res": (p.GetSetting("timelineResolutionWidth"), p.GetSetting("timelineResolutionHeight")),
    }
    return p, info


def map_project(project, timeline_name: Optional[str] = None) -> Dict:
    """List timelines and bins, plus one timeline's video tracks with items and markers.

    Run first in any session to snapshot the layout before a destructive step. `timeline_name` defaults
    to the current timeline. Items come back as (name, start, duration, color) with start relative to
    the timeline start.
    """
    tls = list_timelines(project)
    cut = find_timeline(project, timeline_name) if timeline_name else project.GetCurrentTimeline()
    out = {
        "project": project.GetName(),
        "timelines": [t.GetName() for t in tls],
        "bins": list_bins(project.GetMediaPool()),
        "fps": project.GetSetting("timelineFrameRate"),
    }
    if cut:
        m = map_timeline(cut)
        out["tracks"] = m["tracks"]
        out["markers"] = m["markers"]
    return out
