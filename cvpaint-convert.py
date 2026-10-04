#!/usr/bin/env python3
from __future__ import annotations

"""
cvpaint-convert v0.2.6

Based on v0.2.5, but improves the GLOBAL palette selection.

Main change:
- v0.2.5 used a greedy global-palette chooser.
- v0.2.6 evaluates every possible fixed-size TMS9918 palette subset
  (with black and white always included) and chooses the subset with the
  lowest total sampled-image error.

For 8 colors total, this means choosing the best 6 colors from the 13
non-black/non-white TMS colors: only 1,716 combinations, which is practical.

Everything else stays intentionally close to the v0.2/v0.2.5 family.

Output:
- raw 12,288-byte ColecoVision CV Paint / PATCOL .PC
"""

import argparse
import sys
from pathlib import Path
from itertools import combinations, combinations_with_replacement
from collections import Counter

try:
    from PIL import Image, ImageOps
except ImportError:
    print("ERROR: Pillow is required.", file=sys.stderr)
    raise SystemExit(2)

WIDTH = 256
HEIGHT = 192
PC_SIZE = 12288
TABLE_SIZE = 6144

TMS9918_PALETTE = [
    (0,   0,   0),     # 0 transparent
    (0,   0,   0),     # 1 black
    (33,  200, 66),    # 2 medium green
    (94,  220, 120),   # 3 light green
    (84,  85,  237),   # 4 dark blue
    (125, 118, 252),   # 5 light blue
    (212, 82,  77),    # 6 dark red
    (66,  235, 245),   # 7 cyan
    (252, 85,  84),    # 8 medium red
    (255, 121, 120),   # 9 light red
    (212, 193, 84),    # 10 dark yellow
    (230, 206, 128),   # 11 light yellow
    (33,  176, 59),    # 12 dark green
    (201, 91, 186),    # 13 magenta
    (204, 204, 204),   # 14 gray
    (255, 255, 255),   # 15 white
]

VALID_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}

RESAMPLERS = {
    "box": Image.Resampling.BOX,
    "bilinear": Image.Resampling.BILINEAR,
    "bicubic": Image.Resampling.BICUBIC,
    "lanczos": Image.Resampling.LANCZOS,
    "nearest": Image.Resampling.NEAREST,
}


def perceptual_distance_sq(a, b):
    dr = a[0] - b[0]
    dg = a[1] - b[1]
    db = a[2] - b[2]
    return 30 * dr * dr + 59 * dg * dg + 11 * db * db


def nearest_palette_index(rgb, allowed):
    best_idx = None
    best_err = None
    for idx in allowed:
        err = perceptual_distance_sq(rgb, TMS9918_PALETTE[idx])
        if best_err is None or err < best_err:
            best_err = err
            best_idx = idx
    return best_idx


def prepare_image(img: Image.Image, fit: str, resample_name: str, background=(0, 0, 0)) -> Image.Image:
    img = img.convert("RGB")
    resample = RESAMPLERS[resample_name]

    if fit == "stretch":
        return img.resize((WIDTH, HEIGHT), resample)

    if fit == "crop":
        return ImageOps.fit(
            img,
            (WIDTH, HEIGHT),
            method=resample,
            centering=(0.5, 0.5),
        )

    if fit == "contain":
        contained = ImageOps.contain(img, (WIDTH, HEIGHT), method=resample)
        canvas = Image.new("RGB", (WIDTH, HEIGHT), background)
        x = (WIDTH - contained.width) // 2
        y = (HEIGHT - contained.height) // 2
        canvas.paste(contained, (x, y))
        return canvas

    raise ValueError(f"Unknown fit mode: {fit}")


def build_weighted_samples(img: Image.Image, sample_step: int = 2):
    """
    Sample the resized image and collapse identical RGB values into weighted entries.

    Pure black pixels are skipped because black is always forced into the global palette
    and the contain-mode letterbox would otherwise dominate the optimization.
    """
    px = img.load()
    counts = Counter()

    for y in range(0, HEIGHT, sample_step):
        for x in range(0, WIDTH, sample_step):
            rgb = px[x, y]
            if rgb[0] < 8 and rgb[1] < 8 and rgb[2] < 8:
                continue
            counts[rgb] += 1

    return list(counts.items())


def select_global_palette_optimal(img: Image.Image, count: int, sample_step: int = 2):
    """
    Exhaustively choose the lowest-error global TMS palette subset.

    Black (1) and white (15) are always included.
    """
    count = max(2, min(15, count))

    mandatory = (1, 15)
    choose_n = count - len(mandatory)

    if choose_n <= 0:
        return mandatory

    candidates = tuple(range(2, 15))  # 2..14 inclusive
    samples = build_weighted_samples(img, sample_step=sample_step)

    if not samples:
        return mandatory

    # Precompute error from every unique sampled color to every candidate color.
    sample_rgbs = [rgb for rgb, _weight in samples]
    sample_weights = [weight for _rgb, weight in samples]

    distances = []
    for rgb in sample_rgbs:
        distances.append(
            [perceptual_distance_sq(rgb, TMS9918_PALETTE[i]) for i in range(16)]
        )

    # Error against mandatory black/white.
    mandatory_best = [
        min(row[1], row[15])
        for row in distances
    ]

    best_palette = None
    best_total = None

    for extra in combinations(candidates, choose_n):
        total = 0

        for n, row in enumerate(distances):
            d = mandatory_best[n]
            for idx in extra:
                if row[idx] < d:
                    d = row[idx]

            total += d * sample_weights[n]

            # Early exit when this candidate can no longer beat the current best.
            if best_total is not None and total >= best_total:
                break

        if best_total is None or total < best_total:
            best_total = total
            best_palette = mandatory + extra

    return tuple(sorted(best_palette))


def choose_best_pair_from_segment(original_pixels, mapped_indices, global_palette, candidate_limit=4):
    """
    v0.2-style local pair selection restricted to the image-level global palette.
    """
    counts = Counter(mapped_indices)
    ordered = [idx for idx, _count in counts.most_common(candidate_limit)]

    if len(ordered) < 2:
        for idx in global_palette:
            if idx not in ordered:
                ordered.append(idx)
            if len(ordered) >= 2:
                break

    if not ordered:
        ordered = [15, 1]

    best = None
    best_error = None

    for c1, c2 in combinations_with_replacement(ordered, 2):
        error = 0
        pattern = 0

        for x, rgb in enumerate(original_pixels):
            d1 = perceptual_distance_sq(rgb, TMS9918_PALETTE[c1])
            d2 = perceptual_distance_sq(rgb, TMS9918_PALETTE[c2])

            if d1 <= d2:
                error += d1
                pattern |= 1 << (7 - x)
            else:
                error += d2

            if best_error is not None and error >= best_error:
                break

        if best_error is None or error < best_error:
            best_error = error
            best = (c1, c2, pattern)

    return best


def tms_offset(x_block: int, y: int) -> int:
    return ((y // 8) * 32 + x_block) * 8 + (y & 7)


def encode_image(img: Image.Image, global_color_count: int):
    if img.size != (WIDTH, HEIGHT):
        raise ValueError("Image must be exactly 256x192 before encoding")

    global_palette = select_global_palette_optimal(img, global_color_count)
    px = img.load()

    pattern = bytearray(TABLE_SIZE)
    color = bytearray(TABLE_SIZE)

    for y in range(HEIGHT):
        for xb in range(32):
            segment_rgb = [px[xb * 8 + i, y] for i in range(8)]
            segment_mapped = [
                nearest_palette_index(rgb, global_palette)
                for rgb in segment_rgb
            ]

            fg, bg, patt = choose_best_pair_from_segment(
                segment_rgb,
                segment_mapped,
                global_palette,
            )

            off = tms_offset(xb, y)
            pattern[off] = patt
            color[off] = ((fg & 0x0F) << 4) | (bg & 0x0F)

    return bytes(pattern + color), global_palette


def decode_pc_bytes(data: bytes) -> Image.Image:
    if len(data) != PC_SIZE:
        raise ValueError(f"Expected {PC_SIZE} bytes, got {len(data)}")

    pattern = data[:TABLE_SIZE]
    color = data[TABLE_SIZE:]

    out = Image.new("RGB", (WIDTH, HEIGHT))
    opx = out.load()

    for y in range(HEIGHT):
        for xb in range(32):
            off = tms_offset(xb, y)
            patt = pattern[off]
            col = color[off]

            fg = (col >> 4) & 0x0F
            bg = col & 0x0F

            fg_rgb = TMS9918_PALETTE[fg] if fg else (0, 0, 0)
            bg_rgb = TMS9918_PALETTE[bg] if bg else (0, 0, 0)

            for i in range(8):
                bit = patt & (1 << (7 - i))
                opx[xb * 8 + i, y] = fg_rgb if bit else bg_rgb

    return out


def convert_one(src, dst, fit, resample_name, global_color_count, preview_dir, dry_run):
    if dst.exists() and not dry_run:
        print(f"[SKIP exists] {dst}")
        return False

    if dry_run:
        print(f"[DRY RUN] {src} -> {dst}")
        return True

    with Image.open(src) as im:
        prepared = prepare_image(im, fit, resample_name)
        data, global_palette = encode_image(prepared, global_color_count)

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)

    if preview_dir is not None:
        preview_dir.mkdir(parents=True, exist_ok=True)
        decode_pc_bytes(data).save(preview_dir / f"{dst.stem}.png")

    palette_text = ",".join(str(i) for i in global_palette)
    print(f"[OK] {src.name} -> {dst.name}  palette=[{palette_text}]")
    return True


def convert_directory(src_dir, dst_dir, fit, resample_name, global_color_count, preview_dir, dry_run):
    files = sorted(
        p for p in src_dir.iterdir()
        if p.is_file() and p.suffix.lower() in VALID_EXTS
    )

    if not files:
        print(f"No supported images found in {src_dir}", file=sys.stderr)
        return 1

    converted = 0
    for src in files:
        dst = dst_dir / f"{src.stem}.pc"
        if convert_one(
            src, dst, fit, resample_name, global_color_count, preview_dir, dry_run
        ):
            converted += 1

    print(f"\nProcessed: {len(files)}")
    print(f"Converted/planned: {converted}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="cvpaint-convert",
        description="Convert artwork to AtariMax/ColecoVision CV Paint .PC format.",
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fit", choices=("contain", "crop", "stretch"), default="contain")
    parser.add_argument(
        "--resample",
        choices=tuple(RESAMPLERS.keys()),
        default="box",
        help="Resize filter (default: box)",
    )
    parser.add_argument(
        "--global-colors",
        type=int,
        default=8,
        help="Total TMS colors for this image, including black/white (default: 8)",
    )
    parser.add_argument("--preview-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    src = args.input.expanduser().resolve()
    dst = args.output.expanduser().resolve()
    preview_dir = args.preview_dir.expanduser().resolve() if args.preview_dir else None

    if not src.exists():
        print(f"ERROR: Input does not exist: {src}", file=sys.stderr)
        return 2

    if src.is_dir():
        return convert_directory(
            src,
            dst,
            args.fit,
            args.resample,
            args.global_colors,
            preview_dir,
            args.dry_run,
        )

    if src.suffix.lower() not in VALID_EXTS:
        print(f"ERROR: Unsupported input type: {src.suffix}", file=sys.stderr)
        return 2

    if dst.suffix.lower() != ".pc":
        if dst.exists() and dst.is_dir():
            dst = dst / f"{src.stem}.pc"
        elif dst.suffix == "":
            dst.mkdir(parents=True, exist_ok=True)
            dst = dst / f"{src.stem}.pc"
        else:
            print("ERROR: Single-file output must end in .pc", file=sys.stderr)
            return 2

    convert_one(
        src,
        dst,
        args.fit,
        args.resample,
        args.global_colors,
        preview_dir,
        args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
