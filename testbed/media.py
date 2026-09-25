"""Generate the testbed media: self-describing cards readable by eye and by machine.

Every video frame shows its source name in large type, a frame counter and timecode on a solid color,
and a barcode strip along the bottom: 4 bits of source ID and 16 bits of frame number, drawn as white
blocks between two fixed white guard blocks. Every audio channel carries a voice counting the seconds
plus a quiet sine at a frequency unique to that source and channel.

    python3 -m testbed.media [out_dir]

Needs ffmpeg and macOS `say`. Files that already exist are kept.
"""
import os
import subprocess
import sys

FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
W, H = 1920, 1080
BLOCK = 40                      # barcode block size in pixels
BAR_Y = H - 2 * BLOCK           # top of the barcode strip
BAR_X = 2 * BLOCK               # left of the first guard block
ID_BITS, FRAME_BITS = 4, 16

# name, file, source ID, fps, seconds, background color, channel tones (Hz), start timecode
VIDEO = [
    ("CAM A · 24p", "cam_a_24p.mov", 1, 24, 30, "0x1F4E79", (440, 550), "10:00:00:00"),
    ("CAM B · 25p", "cam_b_25p.mov", 2, 25, 30, "0x2E7D32", (470, 590), "11:00:00:00"),
    ("CAM C · 30p", "cam_c_30p.mov", 3, 30, 20, "0x8E3B2F", (500, 630), "12:00:00:00"),
    ("SCREEN · 60p", "screen_60p.mov", 4, 60, 20, "0x4A4A4A", (530,), "13:00:00:00"),
    ("GFX v1", "gfx_v1.mov", 5, 24, 10, "0x00796B", (), "00:00:00:00"),
    ("GFX v2", "gfx_v2.mov", 6, 24, 12, "0x6A1B9A", (), "00:00:00:00"),
    ("WIDE · 24p", "mc_wide_24p.mov", 7, 24, 30, "0x37474F", (560, 700), "15:00:00:00"),
    ("CLOSE · 25p", "mc_close_25p.mov", 8, 25, 30, "0xAD1457", (590, 740), "15:00:00:00"),
    ("CAM D · 4ch", "cam_d_4ch.mov", 9, 24, 20, "0x5D4037", (300, 350, 400, 450), "14:00:00:00"),
]
EXT_MIC_DELAY = 1.5             # seconds the external recording starts after CAM D


def barcode_layout():
    """[(x, bit_kind, bit_index)] for every block: guards, then ID bits, then frame bits (LSB first)."""
    cells = [("guard", 0)] + [("id", i) for i in range(ID_BITS)] + [("frame", i) for i in range(FRAME_BITS)] + [("guard", 0)]
    return [(BAR_X + i * BLOCK, kind, bit) for i, (kind, bit) in enumerate(cells)]


def _video_filter(name: str, sid: int, fps: int, tc: str) -> str:
    esc_tc = tc.replace(":", r"\:")
    f = [
        "drawgrid=w=160:h=160:t=1:c=white@0.12",
        f"drawtext=fontfile='{FONT}':text='{name}':fontsize=150:fontcolor=white:x=(w-text_w)/2:y=h*0.26",
        f"drawtext=fontfile='{FONT}':text='frame %{{n}}':fontsize=110:fontcolor=white:x=(w-text_w)/2:y=h*0.47",
        f"drawtext=fontfile='{FONT}':timecode='{esc_tc}':rate={fps}:fontsize=70:fontcolor=white@0.8:x=(w-text_w)/2:y=h*0.65",
        f"drawbox=x={BAR_X - BLOCK // 2}:y={BAR_Y - BLOCK // 2}:w={(ID_BITS + FRAME_BITS + 3) * BLOCK}:h={2 * BLOCK}:c=black:t=fill",
    ]
    for x, kind, bit in barcode_layout():
        box = f"drawbox=x={x}:y={BAR_Y}:w={BLOCK}:h={BLOCK}:c=white:t=fill"
        if kind == "id":
            if sid >> bit & 1:
                f.append(box)
        elif kind == "frame":
            f.append(box + f":enable='mod(floor(n/{2 ** bit}),2)'")
        else:
            f.append(box)
    return ",".join(f)


def _count_track(seconds: int, work: str) -> str:
    """A wav of a voice saying 1, 2, 3 ... with each number starting on its second."""
    out = os.path.join(work, f"count_{seconds}.wav")
    if os.path.exists(out):
        return out
    parts = []
    for i in range(1, seconds + 1):
        aiff = os.path.join(work, f"n{i}.aiff")
        if not os.path.exists(aiff):
            subprocess.run(["say", "-v", "Samantha", "-r", "220", "-o", aiff, str(i)], check=True)
        part = os.path.join(work, f"n{i}.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", aiff, "-af", "apad=whole_dur=1,atrim=0:1", "-ar", "48000",
                        "-ac", "1", part], check=True)
        parts.append(part)
    lst = os.path.join(work, f"count_{seconds}.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{os.path.abspath(p)}'\n" for p in parts)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out], check=True)
    return out


def make_video(out_dir: str, work: str, name, fname, sid, fps, seconds, color, tones, tc) -> str:
    path = os.path.join(out_dir, fname)
    if os.path.exists(path):
        return path
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={color}:s={W}x{H}:r={fps}:d={seconds}"]
    if tones:
        cmd += ["-i", _count_track(seconds, work)]
        for hz in tones:
            cmd += ["-f", "lavfi", "-i", f"sine=f={hz}:sample_rate=48000:d={seconds}"]
        n = len(tones)
        graph = f"[0:v]{_video_filter(name, sid, fps, tc)}[v];[1:a]asplit={n}" + "".join(f"[s{i}]" for i in range(n))
        graph += "".join(f";[s{i}][{2 + i}:a]amix=inputs=2:weights='1 0.12':normalize=0[c{i}]" for i in range(n))
        graph += ";" + "".join(f"[c{i}]" for i in range(n)) + (f"amerge=inputs={n}[a]" if n > 1 else "anull[a]")
        cmd += ["-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-c:a", "pcm_s16le"]
    else:
        cmd += ["-vf", _video_filter(name, sid, fps, tc)]
    cmd += ["-c:v", "prores_ks", "-profile:v", "0", "-timecode", tc, "-t", str(seconds), path]
    subprocess.run(cmd, check=True)
    return path


def make_ext_mic(out_dir: str, work: str, seconds: int = 20) -> str:
    """Mono 'external mic' for CAM D: the same counting voice, starting EXT_MIC_DELAY seconds into CAM D's take."""
    path = os.path.join(out_dir, "ext_mic.wav")
    if os.path.exists(path):
        return path
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", _count_track(seconds, work), "-f", "lavfi", "-i",
                    f"sine=f=660:sample_rate=48000:d={seconds}", "-filter_complex",
                    f"[0:a]atrim=start={EXT_MIC_DELAY}[v];[v][1:a]amix=inputs=2:weights='1 0.12':normalize=0,atrim=0:{seconds - EXT_MIC_DELAY}[a]",
                    "-map", "[a]", "-ac", "1", "-c:a", "pcm_s16le", path], check=True)
    return path


def make_music(out_dir: str, seconds: int = 40) -> str:
    """Stereo 'music': a note that steps up a C major scale every second, left and right an octave apart."""
    path = os.path.join(out_dir, "music.wav")
    if os.path.exists(path):
        return path
    scale = [261.63, 293.66, 329.63, 349.23, 392.0, 440.0, 493.88, 523.25]
    expr = "+".join(f"between(t,{i},{i}.999)*sin(2*PI*{scale[i % 8]}*t)" for i in range(seconds))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"aevalsrc='0.3*({expr})|0.3*({expr.replace('*PI*', '*PI*2*')})':s=48000:d={seconds}",
                    "-c:a", "pcm_s16le", path], check=True)
    return path


def make_still(out_dir: str) -> str:
    path = os.path.join(out_dir, "icon.png")
    if os.path.exists(path):
        return path
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0xF9A825:s=512x512:d=1",
                    "-vf", f"drawtext=fontfile='{FONT}':text='STILL':fontsize=120:fontcolor=black:x=(w-text_w)/2:y=(h-text_h)/2",
                    "-frames:v", "1", path], check=True)
    return path


def generate(out_dir: str) -> list:
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(out_dir, ".work")
    os.makedirs(work, exist_ok=True)
    made = [make_video(out_dir, work, *v) for v in VIDEO]
    return made + [make_ext_mic(out_dir, work), make_music(out_dir), make_still(out_dir)]


def decode_frame(tif_path: str):
    """Read (source ID, frame number) from a rendered frame's barcode, or None when no barcode is visible.

    The frame is scaled to the barcode's native 1920x1080 grid through ffmpeg and sampled at each
    block's center, so any render resolution works as long as the source fills the frame unscaled.
    """
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", tif_path, "-vf", f"scale={W}:{H}", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    def lit(x):
        cx, cy = x + BLOCK // 2, BAR_Y + BLOCK // 2
        return raw[cy * W + cx] > 128
    cells = barcode_layout()
    if not (lit(cells[0][0]) and lit(cells[-1][0])):
        return None
    sid = sum(1 << bit for x, kind, bit in cells if kind == "id" and lit(x))
    frame = sum(1 << bit for x, kind, bit in cells if kind == "frame" and lit(x))
    return sid, frame


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "media")
    for p in generate(out):
        print(p)
