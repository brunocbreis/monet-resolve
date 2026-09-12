"""Clear the music track and lay cues with name, color, volume and fades. See mr.audio.place_music."""
TIMELINE = "Raycast AI Update - Cut v1"; TRACK = 3; MUSIC_BIN = "music"
CUES = [("MUSIC · Ziggy - Walk the Walk (intro)", "Ziggy - Walk the Walk.wav", 0, 961, 0, -10, 12, 24),
        ("MUSIC · Aves - Roasted (what's new)", "Aves - Roasted.wav", 0, 1327, 961, -18, 12, 24),
        ("MUSIC · Danny Shields - Battery Bass (demos)", "Danny Shields - Battery Bass.wav", 0, 3096, 2288, -18, 12, 36),
        ("MUSIC · Ziggy - Walk the Walk (pricing + outro, ending on Cheers)", "Ziggy - Walk the Walk.wav", 1035, 3384, 5436, -10, 24, 12)]
t = mr.find_timeline(project, TIMELINE)
result = mr.audio.place_music(resolve, project, t, TRACK, mr.find_bin(project.GetMediaPool(), MUSIC_BIN), CUES, clear_track=True)
