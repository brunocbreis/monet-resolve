"""monet-resolve: the DaVinci Resolve scripting API plus the functions it is missing.

Same objects as Blackmagic's API (Resolve, Project, Timeline, TimelineItem, MediaPool ...), same
vocabulary, no subclassing. Our functions take those objects as arguments and return plain data.
Importing this package does not connect to Resolve; call `connect()` for that.
"""
from .connect import connect, ResolveNotRunning
from . import _util, projects, timelines, media, assembly, titles, markers, audio, transcription, edit, color, render, gfx, transitions, qc, ui, multicam, richtext, clips
from ._util import tc, timeline_fps, find_timeline, list_timelines, items, clean_name, track_locks, save
from .projects import load_project, map_project
from .timelines import map_timeline, backup_timeline, place_playhead, refresh_timeline
from .media import (walk_folders, list_bins, find_bin, find_clip, import_to_bin, import_file_once, replace_clip_file,
                    cleanup_scratch)
from .assembly import (build_cut_from_list, close_gap_ripple, find_destination_track, insert_fusion_comp_at,
                       nest_timeline_over_placeholder, swap_gfx_clip, place_clips_on_track, place_shots, insert_gap_ripple, SNAPSHOT_KEYS)
from .titles import (insert_fusion_title, insert_fusion_composition, style_text_plus, text_placeholders,
                     title_fitted_to_clip, fusion_vignette_layer)
from .markers import beat_markers
from .audio import (sync_external_audio, set_clip_audio_mapping, remap_timeline_audio_items, audio_crossfades,
                    place_music, resync_item_mappings, DIALOGUE_MONO_CAMERA_STEREO)
from .transcription import transcribe_clip, transcribe_words, transcribe_timeline_range
from .edit import punch_in_clips, alternate_punch_ins, freeze_item
from .color import grade_all_clips, set_input_color_space, export_stills
from .render import render_frame_tiff, render_timeline_mp4
from .gfx import create_gfx_timeline_from_clip
from .transitions import build_push, add_push_transition
from .multicam import angle_numbers, multicam_frame, place_multicam, set_angles, swap_to_multicam
from .clips import (append_exact, continue_clip, merge_through_edits, shift_markers, ripple_insert, items_in_range,
                    place_still)
from .richtext import generators_in_drp, replace_text, title_drt, make_template_drt, import_title_as_clip

__version__ = "0.2.0"
__all__ = [
    "connect", "ResolveNotRunning",
    "projects", "timelines", "media", "assembly", "titles", "markers", "audio", "transcription", "edit", "color", "render", "gfx", "transitions",
    "build_push", "add_push_transition",
    "tc", "timeline_fps", "find_timeline", "list_timelines", "items", "clean_name", "track_locks", "save",
    "load_project", "map_project",
    "map_timeline", "backup_timeline", "place_playhead", "refresh_timeline",
    "walk_folders", "list_bins", "find_bin", "find_clip", "import_to_bin", "import_file_once", "replace_clip_file", "cleanup_scratch",
    "build_cut_from_list", "close_gap_ripple", "find_destination_track", "insert_fusion_comp_at",
    "nest_timeline_over_placeholder", "swap_gfx_clip", "place_clips_on_track", "place_shots", "insert_gap_ripple", "SNAPSHOT_KEYS",
    "insert_fusion_title", "insert_fusion_composition", "style_text_plus", "text_placeholders", "title_fitted_to_clip",
    "fusion_vignette_layer",
    "beat_markers",
    "sync_external_audio", "set_clip_audio_mapping", "remap_timeline_audio_items", "audio_crossfades", "place_music",
    "DIALOGUE_MONO_CAMERA_STEREO",
    "transcribe_clip", "transcribe_words", "transcribe_timeline_range",
    "punch_in_clips", "alternate_punch_ins", "freeze_item",
    "grade_all_clips", "set_input_color_space", "export_stills",
    "render_frame_tiff", "render_timeline_mp4",
    "create_gfx_timeline_from_clip",
    "ui", "multicam", "richtext", "clips", "resync_item_mappings",
    "angle_numbers", "multicam_frame", "place_multicam", "set_angles", "swap_to_multicam",
    "append_exact", "continue_clip", "merge_through_edits", "shift_markers", "ripple_insert", "items_in_range", "place_still",
    "generators_in_drp", "replace_text", "title_drt", "make_template_drt", "import_title_as_clip",
]
