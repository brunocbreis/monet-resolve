"""Replace the clip on a GFX timeline with a newly rendered file; delete older versions from the bin. See mr.assembly.swap_gfx_clip."""
PATH = "/Users/brunoreis/Work/raycast-ai-updates/harness-broll/harness-4k-v20.mov"
BIN = "gfx"; GFX_TIMELINE = "GFX - Harness b-roll"; FRAMES = 274
result = mr.assembly.swap_gfx_clip(resolve, project, PATH, mr.find_bin(project.GetMediaPool(), BIN), mr.find_timeline(project, GFX_TIMELINE), FRAMES, delete_old_versions=True)
