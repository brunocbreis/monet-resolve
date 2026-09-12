"""Insert a native Fusion composition of exact length at a frame on a track without rippling. See mr.assembly.insert_fusion_comp_at."""
TIMELINE = "Raycast AI Update - Cut v2"; TRACK = 2; START = 920; DUR = 274
NAME = "TITLE - Harness"; COLOR = "Violet"; COMP_PATH = None
cut = mr.find_timeline(project, TIMELINE)
result = mr.assembly.insert_fusion_comp_at(resolve, project, cut, TRACK, START, DUR, NAME, color=COLOR, comp_path=COMP_PATH)
