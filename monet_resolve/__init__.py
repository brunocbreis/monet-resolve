"""monet-resolve: the DaVinci Resolve scripting API plus the functions it is missing.

Same objects as Blackmagic's API (Resolve, Project, Timeline, TimelineItem, MediaPool ...), same
vocabulary, no subclassing. Functions take those objects as arguments and return plain data.
Importing this package does not connect to Resolve; call `connect()` for that.
"""
from .connect import connect, ResolveNotRunning
from . import qc, ui
from ._util import (VIDEO_PROPS, add_tracks_until, clean_name, find_timeline, items, list_timelines, save, tc,
                    source_frames, tc_seconds, timeline_fps, track_locks)
from .projects import load_project, map_project
from .timelines import map_timeline, backup_timeline, place_playhead, refresh_timeline
from .media import (walk_folders, list_bins, find_bin, find_clip, import_to_bin, import_file_once, replace_clip_file,
                    cleanup_scratch)
from .assembly import (build_cut_from_list, build_synced_cut, close_gap_ripple, find_destination_track,
                       insert_fusion_comp_at, insert_gap_ripple, nest_timeline_over_placeholder, place_clips_on_track,
                       place_shots, swap_gfx_clip)
from .titles import (insert_fusion_title, insert_fusion_composition, style_text_plus, text_placeholders,
                     title_fitted_to_clip, retrim_title, fusion_vignette_layer)
from .markers import beat_markers
from .audio import (sync_external_audio, set_clip_audio_mapping, remap_timeline_audio_items, resync_item_mappings,
                    audio_crossfades, place_music, DIALOGUE_MONO_CAMERA_STEREO)
from .transcription import transcribe_clip, transcribe_words, transcribe_timeline_range
from .edit import punch_in_clips, alternate_punch_ins, freeze_item
from .color import grade_all_clips, set_input_color_space, export_stills
from .render import render_frame_tiff, render_timeline_mp4
from .gfx import create_gfx_timeline_from_clip
from .transitions import build_push, add_push_transition
from .clips import (append_exact, continue_clip, merge_through_edits, shift_markers, ripple_insert, items_in_range,
                    place_still)
from .multicam import angle_numbers, multicam_frame, place_multicam, set_angles, swap_to_multicam

__version__ = "0.2.0"
