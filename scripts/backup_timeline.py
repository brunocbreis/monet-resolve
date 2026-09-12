"""Duplicate a timeline as a backup and move the copy into the backups bin. See mr.timelines.backup_timeline."""
TIMELINE = "Raycast AI Update - Cut v1"; BACKUP_NAME = "Cut v1 - backup 03 (before tighten)"; TIMELINE_BIN = "timelines"; BACKUPS_BIN = "backups"
t = mr.find_timeline(project, TIMELINE)
result = mr.timelines.backup_timeline(resolve, project, t, BACKUP_NAME, timeline_bin=TIMELINE_BIN, backups_bin=BACKUPS_BIN)
