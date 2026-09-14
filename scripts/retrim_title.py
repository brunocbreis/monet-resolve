"""Change one Text+ title's duration in place; titles to its right keep their positions. See mr.titles.retrim_title."""
TIMELINE = "Raycast AI Update - Cut v2"; OTHER = "Raycast AI Update - Selects (all takes)"
TRACK = 2; START = 3846; DURATION = 247
t = mr.find_timeline(project, TIMELINE); o = mr.find_timeline(project, OTHER)
result = mr.titles.retrim_title(resolve, project, t, TRACK, START, DURATION, other=o)
