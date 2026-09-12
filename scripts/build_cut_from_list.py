"""Build a timeline from a cut list of source ranges on the footage clip. See mr.assembly.build_cut_from_list."""
TIMELINE = "Raycast AI Update - Cut v1"; TIMELINE_BIN = "timelines"; FOOTAGE_BIN = "footage"
VIDEO_TRACKS = ["A-ROLL", "B-ROLL placeholders"]; AUDIO_TRACKS = [("stereo", "VO ext mic"), ("stereo", "Camera mic (backup)")]
CUT = [{"id": "L01", "label": "intro", "src_in": 1000, "src_out": 1249, "section": "INTRO", "broll": "", "gap": 0, "jump": False},
       {"id": "L02", "label": "what is new", "src_in": 2000, "src_out": 2249, "section": "WHAT'S NEW", "broll": "Harness b-roll", "gap": 12, "jump": False}]
mp = project.GetMediaPool()
footage = mr.find_bin(mp, FOOTAGE_BIN).GetClipList()[0]
result = mr.assembly.build_cut_from_list(resolve, project, TIMELINE, CUT, footage, mr.find_bin(mp, TIMELINE_BIN), video_tracks=VIDEO_TRACKS, audio_tracks=AUDIO_TRACKS)
