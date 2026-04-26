import librosa
import numpy as np
from PIL import Image, ImageDraw
import subprocess
import os
import sys

def analyze_audio(mp3_path, fps, n_bars):
    """Load audio file and compute per-frame bar heights from frequency spectrum."""
    y, sr = librosa.load(mp3_path, sr=None, mono=True)

    hop_length = sr // fps
    n_fft = 4096

    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop_length))
    S_db = librosa.amplitude_to_db(S, ref=np.max)

    freq_bins = S_db.shape[0]
    n_frames = S_db.shape[1]

    edges = np.geomspace(1, freq_bins, n_bars + 1)
    edges = np.round(edges).astype(int)

    for i in range(1, len(edges)):
        edges[i] = max(edges[i], edges[i - 1] + 1)
    edges = np.clip(edges, 0, freq_bins - 1)

    bars = np.zeros((n_frames, n_bars))
    for j in range(n_bars):
        bars[:, j] = S_db[edges[j]:edges[j + 1], :].mean(axis=0)

    bars = (bars - bars.min()) / (bars.max() - bars.min() + 1e-8)

    smoothing = 0.45
    for i in range(1, n_frames):
        bars[i] = bars[i] * (1.0 - smoothing) + bars[i - 1] * smoothing

    return bars, n_frames


def render_bar(draw, x0, y_top, x1, y_bottom, outline_w, color_rgba):
    """Draw a single rectangle with black outline and dynamic color."""
    draw.rectangle(
        [x0 - outline_w, y_top - outline_w,
         x1 + outline_w, y_bottom + outline_w],
        fill=(0, 0, 0, 255),
    )
    draw.rectangle(
        [x0, y_top, x1, y_bottom],
        fill=color_rgba,
    )


def get_ffmpeg_path():
    """Resolve FFmpeg path depending on the platform and PyInstaller bundled state."""
    if sys.platform == "win32":
        # PyInstaller extracts to sys._MEIPASS at runtime
        if hasattr(sys, '_MEIPASS'):
            bundled_ffmpeg = os.path.join(sys._MEIPASS, 'ffmpeg.exe')
            if os.path.exists(bundled_ffmpeg):
                return bundled_ffmpeg
        
        # Local Windows execution without PyInstaller
        local_ffmpeg = os.path.join(os.path.dirname(__file__), 'ffmpeg.exe')
        if os.path.exists(local_ffmpeg):
            return local_ffmpeg
            
    # Fallback for Linux testing or if bundled binary isn't found
    return "ffmpeg"


def build_ffmpeg_cmd(ffmpeg_path, output_path, width, height, fps, preview):
    """Build ffmpeg command using explicit ffmpeg path."""
    base = [
        ffmpeg_path, "-y", "-hide_banner", "-loglevel", "warning",
        "-f", "rawvideo",
        "-pix_fmt", "rgba",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "-",
    ]

    if preview:
        return base + [
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "23",
            output_path,
        ]
    else:
        return base + [
            "-c:v", "libvpx-vp9",
            "-pix_fmt", "yuva420p",
            "-b:v", "2M",
            "-auto-alt-ref", "0",
            output_path,
        ]


def hex_to_rgba(hex_color):
    """Convert hex string (e.g. #FFD700) to RGBA tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return (r, g, b, 255)
    elif len(hex_color) == 8:
        r, g, b, a = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4, 6))
        return (r, g, b, a)
    return (255, 215, 0, 255) # Fallback to gold


def create_spectrum_video_generator(
    input_path,
    width=800,
    height=600,
    fps=30,
    n_bars=16,
    bar_gap=4,
    outline_w=2,
    preview=False,
    color_hex="#FFD700"
):
    """Generator that yields progress dictionary during rendering."""
    # Dynamic output naming next to source file
    base_name = os.path.splitext(input_path)[0]
    ext = ".mp4" if preview else ".webm"
    output_path = f"{base_name}_bars{ext}"

    color_rgba = hex_to_rgba(color_hex)
    
    yield {"status": "analyzing", "progress": 0, "total": 0}
    
    try:
        bars, n_frames = analyze_audio(input_path, fps, n_bars)
    except Exception as e:
        yield {"status": "error", "error_message": f"Audio analysis failed: {str(e)}"}
        return

    bar_w = width // (n_bars + 2)
    total_w = bar_w * n_bars
    x_offset = (width - total_w) // 2

    center_y = height // 2
    max_half_h = int(height * 0.4)

    ffmpeg_path = get_ffmpeg_path()
    cmd = build_ffmpeg_cmd(ffmpeg_path, output_path, width, height, fps, preview)
    
    # On Windows, prevent the FFmpeg console from popping up
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW

    try:
        pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE, creationflags=creation_flags)
    except FileNotFoundError:
        yield {"status": "error", "error_message": f"FFmpeg not found. Expected at: {ffmpeg_path}"}
        return
    except Exception as e:
        yield {"status": "error", "error_message": f"Failed to start FFmpeg: {str(e)}"}
        return

    for i in range(n_frames):
        if preview:
            bg = (30, 10, 50, 255)
        else:
            bg = (0, 0, 0, 0)

        img = Image.new("RGBA", (width, height), bg)
        draw = ImageDraw.Draw(img)

        for j in range(n_bars):
            h = bars[i, j]
            half_h = max(int(h * max_half_h), 2)

            x0 = x_offset + j * bar_w + bar_gap
            x1 = x_offset + (j + 1) * bar_w - bar_gap
            y_top = center_y - half_h
            y_bottom = center_y + half_h

            render_bar(draw, x0, y_top, x1, y_bottom, outline_w, color_rgba)

        try:
            pipe.stdin.write(img.tobytes())
        except BrokenPipeError:
            yield {"status": "error", "error_message": "FFmpeg process died unexpectedly."}
            return

        yield {"status": "rendering", "progress": i + 1, "total": n_frames}

    pipe.stdin.close()
    ret = pipe.wait()

    if ret == 0:
        yield {"status": "done", "output_path": output_path}
    else:
        yield {"status": "error", "error_message": f"FFmpeg exited with error code {ret}"}
