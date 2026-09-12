# Scripting-related changelog entries, Resolve 19.0 to 21.1 (extracted 2026-09-12)

## 19.0.1 (2024-09-04)
* Addressed incorrect GetClipProperty script return values for audio clips.
* Addressed issues with executing compiled Lua scripts on Windows.
* Scripting API support to query audio mapping for timeline clips.
* Scripting API support to query format for audio tracks.

## 19.0.2 (2024-10-02)
* Scripting API support to get and set per-clip custom metadata.
* Scripting API support to get and set source start and end frames.
* Scripting API support to get and set source start and end timecode.
* Scripting API support to get and set media pool selection.
* Scripting API support to query timeline clip positions at subframe precision.
* Scripting API support to append clips to timelines at subframe offsets.

## 19.0.3 (2024-10-17)
* Script APIs to add clips to timeline now support source subframes.

## 19.1 (2024-11-12)
#### Scripting API
* Apply grade from DRX and CDL LUT to layers from the Graph API.

## 20 (2025-05-28)
* AI IntelliScript creates timelines with a user provided script.
* AI IntelliScript creates timelines with a user provided script.
* Transcription engine now offers extended language support.
* Export audio transcriptions with speaker and timecode.
* Export transcriptions with improved phrase and sentence breaks.
* AI IntelliCut to generate ADR Cues using transcription speaker info.
* Scripting API support to link full resolution media.
* Scripting API support to replace media preserving sub clip extents.
* Scripting API support for media pool clip to monitor growing file.

## 20.0.1 (2025-06-30)
* Improved IntelliScript alignment of script and transcribe differences.

## 20.1 (2025-08-07)
* Improved right to left language handling in transcriptions.
* Ability to view transcriptions for clips on the source timeline.
* Scripting API support for voice isolation for audio clips and tracks.
* New Javascript promises API for asynchronous workflow operations.

## 20.2 (2025-09-10)
* Up to 2x faster transcriptions on macOS.
* Scripting API support for adding subtitles in render jobs.
* Scripting API support for setting timeline and media pool clip name.

## 20.2.1 (2025-09-23)
* Addressed issue with getting subtitle text via scripting API.

## 20.2.2 (2025-10-15)
* AI IntelliScript now works with multicam clips.
* Scripting API support to set media location on project creation.
* Scripting API support to query and apply Fairlight presets.
* Addressed issues querying some render formats from scripts.

## 21 (2026-06-03)
* IntelliScript supports Final Draft or plain text screenplay imports.
* Faster audio transcription and improved subtitle word timing.
* Transcription column support in list view.
* OpenFX 1.5 color management APIs for colorspace aware effects.
* Support for USD SDK 25.11 with Hydra 2.0 API for Storm renderer.
* User defined metadata variables in paths, expressions and scripts.
* Background analysis for transcription and audio classification.
* Scripting API support to perform IntelliSearch analysis.
* Scripting API support to perform Slate analysis.
* Scripting API support for Speech Generator.
* Scripting API support to remove motion blur for media clips.
* Scripting API support for media pool audio classification.
* Scripting API support for speaker detection in audio transcription.
* Scripting API to disable all background tasks for current session.

## 21.0.1 (2026-06-24)
* Transcription now honors project settings language.
* RemoveMotionBlur API now uses correct encode parameters.
* Addressed character limit consistency in GenerateSpeech API.

## 21.0.3 (2026-07-22)
* Addressed wrong audio mapping scripting results in some scenarios.
* Scripting API support to list project attributes in a project bin.
* Scripting API support for user preferences presets.
* Scripting API support for listing UI layout presets.
* Scripting API support for listing and deleting data burn in presets.

## 21.0.4 (2026-08-05)
* Scripting API to get timeline clip selection.
* Scripting API to get timeline object from media pool timeline entry.
* SetRenderSettings API options for handles, extents and data burn.
