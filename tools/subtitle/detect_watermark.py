#!/usr/bin/env python3
"""
Watermark detector for subtitle tool.

Samples frames from a specified corner of a video, finds static pixels
(low variance across frames = watermark), and returns the tight bounding box.

Usage:
  python detect_watermark.py <video_input> <corner> <width> <height>
  corner: top-left | top-right | bottom-left | bottom-right

Output (stdout): JSON { "x": int, "y": int, "w": int, "h": int }
         or JSON { "error": "reason" } on failure
"""

import sys
import json
import os
import subprocess
import tempfile
import shutil

VARIANCE_THRESHOLD = 20   # pixels that vary less than this are "static"
BRIGHTNESS_MIN = 8        # exclude near-black pixels (letterbox bars)
MIN_STATIC_PIXELS = 40    # minimum static pixels to consider it a real watermark
PADDING = 5               # extra pixels around detected bounding box


def main():
    if len(sys.argv) < 5:
        out({"error": "Usage: detect_watermark.py <input> <corner> <width> <height>"})
        return

    video_input = sys.argv[1]
    corner = sys.argv[2]
    width = int(sys.argv[3])
    height = int(sys.argv[4])

    try:
        from PIL import Image
    except ImportError:
        out({"error": "Pillow not installed — run: pip install Pillow"})
        return

    # Corner crop region: 25% of video dimensions, minimum 80px
    cw = max(int(width * 0.25), 80)
    ch = max(int(height * 0.25), 80)

    if corner == 'top-left':
        cx, cy = 0, 0
    elif corner == 'top-right':
        cx, cy = width - cw, 0
    elif corner == 'bottom-left':
        cx, cy = 0, height - ch
    elif corner == 'bottom-right':
        cx, cy = width - cw, height - ch
    else:
        out({"error": f"Unknown corner: {corner}"})
        return

    tmpdir = tempfile.mkdtemp()
    try:
        frames = extract_frames(video_input, cx, cy, cw, ch, tmpdir, Image)
        if len(frames) < 3:
            out({"error": f"Only extracted {len(frames)} frames — need at least 3"})
            return

        result = detect_static_region(frames, cx, cy)
        if result is None:
            out({"error": "No watermark detected in region"})
            return

        out(result)
    except Exception as e:
        out({"error": str(e)})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def extract_frames(video_input, cx, cy, cw, ch, tmpdir, Image):
    """Extract frames cropped to corner region using ffmpeg."""
    # Sample at these timestamps (seconds); short videos will just skip missing ones
    timestamps = [5, 15, 30, 50, 75, 105, 140, 180]
    frames = []

    for i, t in enumerate(timestamps):
        out_path = os.path.join(tmpdir, f'frame_{i}.png')
        try:
            subprocess.run(
                [
                    'ffmpeg',
                    '-ss', str(t),
                    '-i', video_input,
                    '-vf', f'crop={cw}:{ch}:{cx}:{cy}',
                    '-vframes', '1',
                    '-y', '-loglevel', 'error',
                    out_path,
                ],
                capture_output=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            try:
                img = Image.open(out_path).convert('RGB')
                img.load()  # force load before tmpdir cleanup
                frames.append(img)
            except Exception:
                pass

    return frames


def detect_static_region(frames, cx, cy):
    """
    Find the bounding box of static (watermark) pixels.
    Static = low variance across frames + not pure black.
    """
    w, h = frames[0].size
    n = len(frames)

    # Convert all frames to grayscale pixel lists
    gray = [list(f.convert('L').getdata()) for f in frames]

    static_xs = []
    static_ys = []

    for idx in range(w * h):
        vals = [gray[f][idx] for f in range(n)]
        variance = max(vals) - min(vals)
        avg = sum(vals) / n

        if variance < VARIANCE_THRESHOLD and avg > BRIGHTNESS_MIN:
            static_xs.append(idx % w)
            static_ys.append(idx // w)

    if len(static_xs) < MIN_STATIC_PIXELS:
        return None

    min_x, max_x = min(static_xs), max(static_xs)
    min_y, max_y = min(static_ys), max(static_ys)

    # Apply padding, clamped to region bounds
    min_x = max(0, min_x - PADDING)
    min_y = max(0, min_y - PADDING)
    max_x = min(w - 1, max_x + PADDING)
    max_y = min(h - 1, max_y + PADDING)

    detected_w = max_x - min_x + 1
    detected_h = max_y - min_y + 1

    # Sanity check: detected region shouldn't be the whole crop (false positive)
    if detected_w >= w * 0.9 and detected_h >= h * 0.9:
        return None

    return {
        'x': cx + min_x,
        'y': cy + min_y,
        'w': detected_w,
        'h': detected_h,
    }


def out(data):
    print(json.dumps(data))


if __name__ == '__main__':
    main()
