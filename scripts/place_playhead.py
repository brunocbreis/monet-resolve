"""Switch to a timeline, park the playhead at a timecode, save. See mr.timelines.place_playhead."""
TIMELINE = "Raycast AI Update - Cut v2"; TC = "01:00:38:08"
result = mr.timelines.place_playhead(resolve, project, mr.find_timeline(project, TIMELINE), TC)
