"""Media pool: bins, clips, imports, file replacement, scratch cleanup."""
from typing import Dict, Iterable, List, Optional, Sequence, Union

from ._util import list_timelines, save


def walk_folders(folder) -> List:
    """`folder` and every descendant Folder, depth first."""
    out = [folder]
    for c in folder.GetSubFolderList():
        out.extend(walk_folders(c))
    return out


def list_bins(media_pool) -> List[str]:
    """The bin tree as indented 'name/' lines, root first."""
    def walk(f, d=0, out=None):
        out = [] if out is None else out
        out.append("  " * d + f.GetName() + "/")
        for c in f.GetSubFolderList():
            walk(c, d + 1, out)
        return out
    return walk(media_pool.GetRootFolder())


def find_bin(media_pool, path: Union[str, Sequence[str]]):
    """Return the Folder at `path` ('gfx' or ['timelines', 'gfx']) below the root. Raises LookupError.

    The API has no lookup by name; this walks `GetSubFolderList()` level by level.
    """
    names = [path] if isinstance(path, str) else list(path)
    f = media_pool.GetRootFolder()
    for name in names:
        hit = [x for x in f.GetSubFolderList() if x.GetName() == name]
        if not hit:
            raise LookupError(f"no bin named {name!r} under {f.GetName()!r}")
        f = hit[0]
    return f


def find_clip(folder, name: Optional[str] = None, recursive: bool = True):
    """Return the MediaPoolItem named `name` in `folder` (recursing into sub-bins by default).

    `name=None` returns the first clip of `folder`. Returns None when nothing matches.
    """
    for c in folder.GetClipList():
        if name is None or c.GetName() == name:
            return c
    if recursive:
        for sub in folder.GetSubFolderList():
            r = find_clip(sub, name, True)
            if r:
                return r
    return None


def import_to_bin(media_pool, paths: Iterable[str], bin_name: str,
                  props: Sequence[str] = ("FPS", "Resolution", "Duration", "Frames", "Audio Ch", "Sample Rate", "Type")) -> List[Dict]:
    """Import files into a root-level bin (created when missing) and report each clip's properties.

    `ImportMedia` lands in the current bin, so the bin is made current for the import and the root
    restored afterward. Returns [{"name": ..., <prop>: value, ...}].
    """
    root = media_pool.GetRootFolder()
    bins = {f.GetName(): f for f in root.GetSubFolderList()}
    b = bins.get(bin_name) or media_pool.AddSubFolder(root, bin_name)
    media_pool.SetCurrentFolder(b)
    clips = media_pool.ImportMedia(list(paths)) or []
    media_pool.SetCurrentFolder(root)
    return [{"name": c.GetName(), **{k: c.GetClipProperty(k) for k in props}} for c in clips]


def import_file_once(media_pool, folder, path: str):
    """Return the clip in `folder` whose 'File Path' is `path`, importing it into `folder` when absent.

    Leaves `folder` as the current bin (callers restore the root when they need to). Returns None when
    the import fails. Shared by swap_gfx_clip and create_gfx_timeline_from_clip.
    """
    media_pool.SetCurrentFolder(folder)
    have = [c for c in folder.GetClipList() if c.GetClipProperty("File Path") == path]
    return have[0] if have else (media_pool.ImportMedia([path]) or [None])[0]


def replace_clip_file(resolve, folder, replacements: Dict[str, str]) -> List:
    """Point media pool clips in `folder` at new files on disk; every timeline using them follows.

    `replacements` maps clip name to the new absolute path. `MediaPoolItem.ReplaceClip(path)` repoints
    the clip and keeps its pool name. Saves. Returns [(name, ok, frames, file_path)] or (name, "missing").
    """
    clips = {c.GetName(): c for c in folder.GetClipList()}
    log = []
    for name, path in replacements.items():
        c = clips.get(name)
        if not c:
            log.append((name, "missing"))
            continue
        ok = c.ReplaceClip(path)
        log.append((name, bool(ok), c.GetClipProperty("Frames"), c.GetClipProperty("File Path")))
    save(resolve)
    return log


def cleanup_scratch(resolve, project, timelines: Sequence[str] = (), scratch_bin: Optional[str] = None,
                    stray_prefix: Optional[str] = None, confirm: bool = False) -> Dict:
    """Delete probe timelines by name, a root-level scratch bin with its clips, and stray pool items by prefix.

    Destructive and not undoable from the API: `DeleteTimelines`, `DeleteClips`, `DeleteFolders`. Requires
    `confirm=True`; run `map_project` first and check the names. `stray_prefix="Fusion Clip"` removes the
    "Fusion Clip N" items `CreateFusionClip` leaves in the current bin. Saves. Returns what was deleted.
    """
    if not confirm:
        raise ValueError("cleanup_scratch deletes timelines, clips and bins; pass confirm=True")
    mp = project.GetMediaPool()
    root = mp.GetRootFolder()
    sub = {f.GetName(): f for f in root.GetSubFolderList()}
    out = {}
    gone = [x for x in list_timelines(project) if x.GetName() in timelines]
    if gone:
        out["timelines"] = (mp.DeleteTimelines(gone), [x.GetName() for x in gone])
    if scratch_bin and scratch_bin in sub:
        cl = sub[scratch_bin].GetClipList()
        if cl:
            mp.DeleteClips(cl)
        out["bin"] = mp.DeleteFolders([sub[scratch_bin]])
    if stray_prefix:
        stray = [c for f in walk_folders(root) for c in f.GetClipList() if c.GetName().startswith(stray_prefix)]
        if stray:
            out["stray"] = (mp.DeleteClips(stray), [c.GetName() for c in stray])
    save(resolve)
    return out
