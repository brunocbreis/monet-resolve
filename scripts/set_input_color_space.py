"""Set the input color space of a camera clip, trying name variants until one is accepted. See mr.color.set_input_color_space."""
BIN = "footage"; CLIP = None; CANDIDATES = ["Sony S-Gamut/S-Log2", "Sony S-Gamut S-Log2", "S-Gamut/S-Log2"]
c = mr.find_clip(mr.find_bin(project.GetMediaPool(), BIN), CLIP, recursive=False)
result = mr.color.set_input_color_space(resolve, c, CANDIDATES)
