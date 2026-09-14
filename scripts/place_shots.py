"""Shot list onto a track: wide shots, 2.6x close-ups (zoom/pan/tilt) and native freeze frames. See mr.assembly.place_shots.

Close-up framing: CX, CY are the source pixel to centre; K = fit scale x zoom (0.9375 x 2.6 for a 3548x2304
recording on a 4K timeline). Source frames are the clip's own (60p); a range of n lands int(n * 0.4) frames at 24p.
"""
CUT = "Raycast AI Update - Cut v3"; BIN = "screen-recs"; CLIP = "ai-settings.mp4"; TRACK = 4
Z = 2.6; K = 0.9375 * Z; CX = 1816.5
def cu(cy): return {"ZoomX": Z, "ZoomY": Z, "Pan": -(CX - 1774) * K, "Tilt": (cy - 1152) * K}
WIDE = {"ZoomX": 1.155, "ZoomY": 1.155, "Pan": 0.0, "Tilt": 0.0}
mp = project.GetMediaPool()
clip = mr.find_clip(mr.find_bin(mp, BIN), CLIP, recursive=False)
SHOTS = [  # name, record, src_in, src_out, props, freeze
    ("REC - AI Settings, Automations tab (wide)", 2051, 1680, 1968, WIDE, False),
    ("REC - Examples list (close-up, freeze)", 2312, 2190, 2378, cu(1245), True),
    ("REC - Account tab (wide)", 5521, 5166, 5316, WIDE, False),
    ("REC - Credits bar + top up (close-up)", 5581, 5316, 5746, cu(1090), False),
    ("REC - Account tab (wide, freeze)", 5753, 5790, 6078, WIDE, True),
    ("REC - Models & Providers (wide)", 5868, 2856, 3084, WIDE, False),
    ("REC - Local AI Subscriptions connect (close-up)", 5959, 3174, 3450, cu(1221), False),
    ("REC - Models & Providers connected (wide, freeze)", 6069, 3450, 3745, WIDE, True),
    ("REC - Providers page scroll (wide)", 6383, 4074, 4224, WIDE, False),
    ("REC - API keys + custom providers (close-up, freeze)", 6443, 4350, 4700, cu(1161), True),
]
cut = mr.find_timeline(project, CUT)
result = mr.assembly.place_shots(resolve, project, cut, TRACK, [dict(name=n, record=r, clip=clip, src_in=a, src_out=b, props=p, freeze=f) for n, r, a, b, p, f in SHOTS])
