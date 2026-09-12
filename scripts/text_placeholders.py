"""Insert a Text+ placeholder on a track for each span and set its text, font, size and color. See mr.titles.text_placeholders."""
TIMELINE = "Raycast AI Update - Cut v2"; OTHER = "Raycast AI Update - Selects (all takes)"; TRACK = 2; FPS = 24
SPANS = [(920, 1194, "Harness b-roll"), (1194, 1378, "Automations b-roll"), (1378, 1681, "Projects b-roll"), (1681, 2010, "ChatGPT + Claude b-roll")]
FONT = "Inter 28pt"; STYLE = "Medium"; SIZE = 0.045; RGB = (1, 0.85, 0.35)
t = mr.find_timeline(project, TIMELINE); o = mr.find_timeline(project, OTHER)
result = mr.titles.text_placeholders(resolve, project, t, TRACK, SPANS, other=o, font=FONT, style=STYLE, size=SIZE, rgb=RGB, fps=FPS)
