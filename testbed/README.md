# Testbed

A Resolve project, `monet-testbed`, built from generated media, plus one check per library function. A check runs a function on a copy of a base timeline and confirms what moved, what stayed and what was refused, down to the frame and the audio channel.

It covers deterministic timeline operations. Anything that depends on content the library cannot control (transcription, `qc`) stays out.

## Run

    python3 -m testbed.baseline restore   # only when the project is missing or drifted
    python3 -m testbed.run                # every check; `--ui` adds the menu-bar checks
    python3 -m testbed.run freeze_item    # named checks only

`run` first compares the base timelines with the frozen baseline and stops if they differ. Results print as PASS / FAIL and land in `testbed/out/report.json`.

## Reading a check in Resolve

Each check leaves two timelines in `timelines/checks`: `<check> · before`, untouched, and `<check> · after`, with the function applied. The "after" timeline has a marker where it matters, green for PASS and red for FAIL, and the marker's note says what should have happened.

Every clip is a card with its source name, a frame counter and a timecode, and a voice counts the seconds. A jump in the counter or a stutter in the voice shows a bad edit. The barcode strip along the bottom carries the same source and frame for the machine, which reads it from one-frame Deliver renders.

## Changing the baseline

The media and the project are built once and kept locally (`testbed/media`, `testbed/baseline`, both ignored by git). Rebuild only when a new check needs new material:

    python3 -m testbed.build --fresh      # regenerates missing media, recreates the project
    python3 -m testbed.baseline freeze    # after checking the new build in Resolve

## Files

| File | Role |
| --- | --- |
| `media.py` | Generates the cards, tones, counting voice, external mic, music and still; decodes barcodes |
| `build.py` | Creates the project, bins, multicam clip and base timelines (`a-roll`, `layered`, `angles`) |
| `baseline.py` | Freezes, verifies and restores the checked project (a DRT fingerprint per base timeline) |
| `checks.py` | The checks |
| `run.py` | Runs checks and writes the report |

## Open items

- `set_angles` (`--ui`): the menu reports Clip > Multicam Switch disabled with a multicam item selected, and the click changes nothing.
- `richtext`: needs an Edit-page Text title typed by hand once in the baseline; a scripted title stores no text.
- `grade_all_clips` and `set_input_color_space` need a DRX and a color-managed project.
- Comparing whole "after" timelines against approved DRT exports ("golden files"): exports are stable once IDs are normalized, except timelines holding a Fusion composition.
