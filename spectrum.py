import librosa
import numpy as np
from PIL import Image, ImageDraw
import subprocess
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


def render_bar(draw, x0, y_top, x1, y_bottom, outline_w):
    """Draw a single white rectangle with black outline."""

    draw.rectangle(
        [x0 - outline_w, y_top - outline_w,
         x1 + outline_w, y_bottom + outline_w],
        fill=(0, 0, 0, 255),
    )
    draw.rectangle(
        [x0, y_top, x1, y_bottom],
        fill=(135, 206, 235, 245),
    )


def build_ffmpeg_cmd(output_path, width, height, fps, preview):
    """Build ffmpeg command for preview (mp4) or production (webm+alpha)."""

    base = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
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


def create_spectrum_video(
    mp3_path,
    width=800,
    height=600,
    fps=30,
    n_bars=16,
    bar_gap=4,
    outline_w=2,
    preview=False,
):
    if preview:
        output_path = "bars_preview.mp4"
    else:
        output_path = "bars.webm"

    print("Analyzing audio...")
    bars, n_frames = analyze_audio(mp3_path, fps, n_bars)

    bar_w = width // (n_bars + 2)
    total_w = bar_w * n_bars
    x_offset = (width - total_w) // 2

    center_y = height // 2
    max_half_h = int(height * 0.4)

    cmd = build_ffmpeg_cmd(output_path, width, height, fps, preview)
    pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    duration = n_frames / fps
    mode = "PREVIEW" if preview else "PRODUCTION (alpha)"
    print(f"Mode: {mode}")
    print(f"Resolution: {width}x{height}")
    print(f"Rendering {n_frames} frames ({duration:.1f}s at {fps} fps)...")
    print(f"Output: {output_path}")

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

            render_bar(draw, x0, y_top, x1, y_bottom, outline_w)

        pipe.stdin.write(img.tobytes())

        if i % fps == 0:
            print(f"  frame {i}/{n_frames}  ({100 * i // n_frames}%)")

    pipe.stdin.close()
    ret = pipe.wait()

    if ret == 0:
        print(f"Done: {output_path}")
    else:
        print(f"ffmpeg exited with error code {ret}")


if __name__ == "__main__":
    mp3 = None
    preview = False

    for arg in sys.argv[1:]:
        if arg == "--preview":
            preview = True
        else:
            mp3 = arg

    if mp3 is None:
        print("Usage:")
        print("  python spectrum.py song.mp3              -> bars.webm")
        print("  python spectrum.py song.mp3 --preview    -> bars_preview.mp4")
        sys.exit(1)

    create_spectrum_video(
        mp3_path=mp3,
        preview=preview,
    )