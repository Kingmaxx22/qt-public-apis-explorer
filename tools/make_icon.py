"""Generate a multi-resolution Windows .ico, with no Qt dependency.

    python tools/make_icon.py

Written in pure Python (zlib + struct) on purpose: rendering through Qt
segfaults on the offscreen platform, and this script only needs to rasterise
four rounded bars, a disc and four connector lines. Supersampled 4x for
antialiasing, then packed into a real ICO container.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "app.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]

SS = 4  # supersampling factor

# Mirrors theme.PRIMARY / theme.PRIMARY_CONTAINER.
CYAN = (0x4C, 0xD6, 0xFB)
HUB = (0x00, 0xB4, 0xD8)


def _rounded_rect_hit(x: float, y: float, rx: float, ry: float,
                      w: float, h: float, r: float) -> bool:
    if x < rx or x > rx + w or y < ry or y > ry + h:
        return False
    dx = min(x - rx, rx + w - x)
    dy = min(y - ry, ry + h - y)
    if dx < r and dy < r:
        return math.hypot(r - dx, r - dy) <= r
    return True


def _disc_hit(x: float, y: float, cx: float, cy: float, r: float) -> bool:
    return math.hypot(x - cx, y - cy) <= r


def _thick_segment_hit(x, y, ax, ay, bx, by, half_w) -> bool:
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return math.hypot(x - ax, y - ay) <= half_w
    t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length2))
    return math.hypot(x - (ax + t * dx), y - (ay + t * dy)) <= half_w


def render(size: int) -> bytes:
    """Return raw RGBA rows for a `size` x `size` icon."""
    n = size * SS
    s = float(n)
    # Geometry, expressed as fractions of the canvas (matches widgets.Logo).
    bar_w, bar_h = 0.22 * s, 0.64 * s
    bar_y, bar_r = 0.18 * s, max(1.0, 0.03 * s)
    left_x, right_x = 0.0, 0.78 * s
    hub_c, hub_r = 0.5 * s, 0.17 * s
    conn_half = max(0.5, 0.035 * s)

    segments = (
        (0.22 * s, 0.38 * s, 0.40 * s, 0.42 * s),
        (0.22 * s, 0.62 * s, 0.40 * s, 0.58 * s),
        (0.78 * s, 0.38 * s, 0.60 * s, 0.42 * s),
        (0.78 * s, 0.62 * s, 0.60 * s, 0.58 * s),
    )

    big = bytearray(n * n * 4)
    for py in range(n):
        y = py + 0.5
        row = py * n * 4
        for px in range(n):
            x = px + 0.5

            a_r = a_g = a_b = a_a = 0
            for color, hit in (
                (HUB, _disc_hit(x, y, hub_c, hub_c, hub_r)),
                (CYAN,
                 _rounded_rect_hit(x, y, left_x, bar_y, bar_w, bar_h, bar_r)
                 or _rounded_rect_hit(x, y, right_x, bar_y, bar_w, bar_h, bar_r)
                 or any(_thick_segment_hit(x, y, *seg, conn_half)
                        for seg in segments)),
            ):
                if hit:
                    a_r, a_g, a_b, a_a = color[0], color[1], color[2], 255

            i = row + px * 4
            big[i] = a_r
            big[i + 1] = a_g
            big[i + 2] = a_b
            big[i + 3] = a_a

    # Box-downsample the supersampled buffer.
    out = bytearray(size * size * 4)
    area = SS * SS
    for y in range(size):
        for x in range(size):
            r = g = b = a = 0
            for dy in range(SS):
                base = (y * SS + dy) * n * 4 + x * SS * 4
                for dx in range(SS):
                    i = base + dx * 4
                    r += big[i]
                    g += big[i + 1]
                    b += big[i + 2]
                    a += big[i + 3]
            o = (y * size + x) * 4
            out[o] = r // area
            out[o + 1] = g // area
            out[o + 2] = b // area
            out[o + 3] = a // area
    return bytes(out)


def to_png(rgba: bytes, size: int) -> bytes:
    """Minimal RGBA PNG encoder."""
    raw = bytearray()
    stride = size * 4
    for y in range(size):
        raw.append(0)  # filter type 0 (None)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def write_ico(frames: list[bytes], sizes: list[int], out: Path) -> None:
    header = bytearray()
    header += (0).to_bytes(2, "little")
    header += (1).to_bytes(2, "little")
    header += len(frames).to_bytes(2, "little")

    offset = 6 + 16 * len(frames)
    entries = bytearray()
    payload = bytearray()
    for size, blob in zip(sizes, frames):
        dim = 0 if size >= 256 else size
        entries += bytes([dim, dim, 0, 0])
        entries += (1).to_bytes(2, "little")
        entries += (32).to_bytes(2, "little")
        entries += len(blob).to_bytes(4, "little")
        entries += offset.to_bytes(4, "little")
        payload += blob
        offset += len(blob)

    out.write_bytes(bytes(header + entries + payload))


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames = [to_png(render(size), size) for size in SIZES]
    write_ico(frames, SIZES, OUT)
    OUT.with_suffix(".png").write_bytes(frames[-1])

    raw = OUT.read_bytes()
    print(f"Wrote {OUT} ({len(raw):,} bytes, "
          f"{int.from_bytes(raw[4:6], 'little')} sizes: {SIZES})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())