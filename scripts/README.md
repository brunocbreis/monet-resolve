# Scripts

The 29 original task scripts, now thin callers into the `monet_resolve` package. Each keeps its UPPERCASE parameters at the top and sets `result`. Run one with `resolve`, `project` and `mr` pre-bound:

    python -m monet_resolve.run scripts/<name>.py

Or paste the body into the `DaVinci Resolve:run_script` MCP tool after `import monet_resolve as mr`. Function docstrings hold the details and the workaround each one embodies.
- `retrim_title.py` - change one Text+ title's duration in place; the titles to its right keep their positions.
- `swap_to_multicam.py` - replace clips cut from source files with the synced multicam and set each angle.
- `set_multicam_angles.py` - switch multicam items in a range to an angle through the menu bar.
- `copy_text_title.py` - copy a Text title from another project with new words and place it.
- `close_timeline_tabs.py` - close every timeline tab except the ones to keep.
- `run_audio_assistant.py` - run the AI Audio Assistant's Auto Mix and wait for it.
- `extend_take.py` - let a moment run longer on every track (ripple insert plus clip continuations).
