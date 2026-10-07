import argparse
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms

# OpenCV for face detection (optional)
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "calibration"))
import common as C

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PALETTE = ROOT / "palettes" / "inky73_measured.json"
FALLBACK_PALETTE = ROOT / "palettes" / "inky73_nominal.json"

ANCHORS = {
    "center": (0.5, 0.5),
    "top": (0.5, 0.0),
    "bottom": (0.5, 1.0),
    "left": (0.0, 0.5),
    "right": (1.0, 0.5),
}


def load_srgb(path):
    im = Image.open(path)
    im = im.convert("RGB")
    try:
        from PIL import ImageOps

        im = ImageOps.exif_transpose(im)
    except Exception:
        pass
    icc = im.info.get("icc_profile")
    if icc is not None:
        try:
            src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            dst = ImageCms.createProfile("sRGB")
            im = ImageCms.applyTransform(im, ImageCms.buildTransform(src, dst, "RGB", "RGB"))
        except Exception:
            pass
    return im


def cover_crop(im, anchor):
    tw, th = 800, 480
    w, h = im.size
    scale = max(tw / w, th / h)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    ax, ay = ANCHORS[anchor]
    x = int((nw - tw) * ax)
    y = int((nh - th) * ay)
    return im.crop((x, y, x + tw, y + th))


def detect_faces(im, min_size=30):
    """Detect faces (human, cat) in image using OpenCV Haar cascades.
    Runs detection on a downscaled image for speed and accuracy.
    Returns list of (x, y, w, h) face boxes in ORIGINAL image coordinates.
    """
    if not CV2_AVAILABLE:
        return []

    # Resize image for detection (max 2000px on longest side to preserve small faces)
    w, h = im.size
    max_detect_dim = 2000
    if max(w, h) > max_detect_dim:
        detect_scale = max_detect_dim / max(w, h)
        detect_w = int(w * detect_scale)
        detect_h = int(h * detect_scale)
        detect_im = im.resize((detect_w, detect_h), Image.LANCZOS)
    else:
        detect_im = im
        detect_scale = 1.0

    # Convert to OpenCV format
    cv_im = cv2.cvtColor(np.array(detect_im), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_im, cv2.COLOR_BGR2GRAY)

    # Load cascades with tuned parameters for each type
    cascade_dir = cv2.data.haarcascades
    cascades = {
        'human': (
            cv2.CascadeClassifier(cascade_dir + "haarcascades/haarcascade_frontalface_default.xml"),
            {'minNeighbors': 9, 'minSize': (30, 30)},
        ),
        'cat': (
            cv2.CascadeClassifier(cascade_dir + "haarcascades/haarcascade_frontalcatface.xml"),
            {'minNeighbors': 1, 'minSize': (20, 25)},
        ),
        'cat_ext': (
            cv2.CascadeClassifier(cascade_dir + "haarcascades/haarcascade_frontalcatface_extended.xml"),
            {'minNeighbors': 2, 'minSize': (20, 25)},
        ),
    }

    all_faces = []
    for name, (cascade, params) in cascades.items():
        if cascade.empty():
            continue
        # Detect on downscaled image - minSize in downscaled coordinates
        faces = cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=params['minNeighbors'],
            minSize=(params['minSize'][0], params['minSize'][1]),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )
        for x, y, fw, fh in faces:
            # Scale back to original image coordinates
            ox = int(x / detect_scale)
            oy = int(y / detect_scale)
            ow = int(fw / detect_scale)
            oh = int(fh / detect_scale)
            # Area in original image coordinates
            orig_area = ow * oh
            all_faces.append((ox, oy, ow, oh, name, orig_area))

    # Filter: keep only reasonably large faces (minimum 20,000 pixels = ~141x141)
    min_area = 20000
    filtered = [f for f in all_faces if f[5] >= min_area]
    
    # Additional filter: face must be at least 4% of max image dimension
    max_dim = max(w, h)
    min_dim_ratio = 0.04  # face must be at least 4% of max image dimension
    filtered = [f for f in filtered if max(f[2], f[3]) >= min_dim_ratio * max_dim]
    
    # If multiple faces, only keep the largest one (most likely to be real)
    if len(filtered) > 1:
        filtered.sort(key=lambda f: f[5], reverse=True)
        filtered = [filtered[0]]
    
    return filtered


def face_center_crop(im, debug_dir=None, img_name="image"):
    """Cover crop with vertical centering on mean face position.
    Only pans vertically; width always fills display (800px).
    """
    tw, th = 800, 480
    w, h = im.size

    # Scale to fill width
    scale = tw / w
    nw, nh = tw, int(round(h * scale))

    # Detect faces on original image
    faces = detect_faces(im)

    # Compute mean face center Y in scaled coordinates
    if faces:
        mean_face_y = sum(y + h // 2 for x, y, w, h, name, area in faces) / len(faces)
        mean_face_y_scaled = mean_face_y * scale
        # Target crop Y to center mean face on display
        target_y = int(round(mean_face_y_scaled - th / 2))
    else:
        # No faces: fall back to center
        target_y = (nh - th) // 2

    # Clamp to valid crop range
    y = max(0, min(target_y, nh - th))
    x = 0  # always full width

    # Resize and crop
    im = im.resize((nw, nh), Image.LANCZOS)
    return im.crop((x, y, x + tw, y + th))


def face_center_crop_debug(im, debug_dir, img_name):
    """Face center crop with debug visualization."""
    tw, th = 800, 480
    w, h = im.size
    scale = tw / w
    nw, nh = tw, int(round(h * scale))

    faces = detect_faces(im)

    # Debug: save face detection visualization
    if debug_dir and faces:
        cv_im = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
        for x, y, w, h, name, area in faces:
            cv2.rectangle(cv_im, (x, y), (x + w, y + h), (0, 255, 0), 3)
            # Draw face center
            cy = y + h // 2
            cv2.circle(cv_im, (x + w // 2, cy), 10, (255, 0, 0), -1)
            # Draw face type
            cv2.putText(cv_im, name, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        # Draw target crop region
        if faces:
            mean_face_y = sum(y + h // 2 for x, y, w, h, name, area in faces) / len(faces)
            mean_face_y_scaled = mean_face_y * scale
            target_y = int(round(mean_face_y_scaled - th / 2))
            target_y = max(0, min(target_y, nh - th))
        else:
            target_y = (nh - th) // 2
        cv2.rectangle(cv_im, (0, int(target_y / scale)), (w, int((target_y + th) / scale)), (255, 0, 0), 3)

        debug_path = debug_dir / f"{img_name}_faces.jpg"
        cv2.imwrite(str(debug_path), cv_im)

    if faces:
        mean_face_y = sum(y + h // 2 for x, y, w, h, name, area in faces) / len(faces)
        mean_face_y_scaled = mean_face_y * scale
        target_y = int(round(mean_face_y_scaled - th / 2))
    else:
        target_y = (nh - th) // 2

    y = max(0, min(target_y, nh - th))
    x = 0

    im = im.resize((nw, nh), Image.LANCZOS)
    return im.crop((x, y, x + tw, y + th))


def contain_pad(im, anchor_name, bg_mode, codes, pal_oklab):
    tw, th = 800, 480
    w, h = im.size
    scale = min(tw / w, th / h)
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    im = im.resize((nw, nh), Image.LANCZOS)

    if bg_mode == "white":
        bg_idx = [i for i, c in enumerate(codes) if tuple(c) == (255, 255, 255)][0]
    elif bg_mode == "black":
        bg_idx = [i for i, c in enumerate(codes) if tuple(c) == (0, 0, 0)][0]
    else:
        arr = np.asarray(im, dtype=float) / 255.0
        mean_ok = C.srgb_to_oklab(arr.reshape(-1, 3)).mean(axis=0)
        bg_idx = int(np.argmin(((pal_oklab - mean_ok) ** 2).sum(axis=1)))

    canvas = Image.new("RGB", (tw, th), tuple(int(v) for v in codes[bg_idx]))
    x = (tw - nw) // 2
    y = (th - nh) // 2
    canvas.paste(im, (x, y))
    return canvas


def apply_saturation(arr01, sat):
    lin = C.srgb_to_linear(arr01)
    lum = lin @ np.array([0.2126, 0.7152, 0.0722])
    out = lum[..., None] + (lin - lum[..., None]) * sat
    return C.linear_to_srgb(out)


def tone_map(coords_img, pal_coords, lo_pct=0.5, hi_pct=99.5):
    """Remap lightness onto the pigments' achievable range (hue/chroma kept).

    Photo content far outside the panel gamut (bright sky, deep shadows)
    otherwise clips flat; stretching only the L axis preserves the image's
    colour character while spreading midtones across the representable band.
    """
    pal = np.asarray(pal_coords, dtype=float)
    l_lo, l_hi = pal[:, 0].min(), pal[:, 0].max()
    p_lo, p_hi = np.percentile(coords_img[..., 0], [lo_pct, hi_pct])
    span = max(p_hi - p_lo, 1e-6)
    out = coords_img.copy()
    out[..., 0] = np.clip(
        l_lo + (coords_img[..., 0] - p_lo) * ((l_hi - l_lo) / span),
        min(l_lo, coords_img[..., 0].min()),
        max(l_hi, coords_img[..., 0].max()),
    )
    return out


def nearest_indices(coords_img, pal):
    flat = coords_img.reshape(-1, 3)
    d = ((flat[:, None, :] - pal[None, :, :]) ** 2).sum(axis=-1)
    return np.argmin(d, axis=1).reshape(coords_img.shape[:2])


def pen_image(idx, codes):
    h, w = idx.shape
    rgb = np.array(codes, dtype=np.uint8)[idx.ravel()].reshape(h, w, 3)
    return Image.fromarray(rgb, "RGB")


def histogram(idx, names, total):
    vals, counts = np.unique(idx, return_counts=True)
    return [(names[v], n, 100.0 * n / total) for v, n in zip(vals.tolist(), counts.tolist())]


def process_image(src, doc, args, debug_root=None):
    """Run one image through the pipeline; return (steps, stats)."""
    names = C.PEN_NAMES
    codes, coords_lab, names_used, _ = C.pen_arrays(doc, space="cielab")
    coords = coords_lab if args.space == "cielab" else C.lab_to_oklab(coords_lab)

    steps = {}
    im = load_srgb(src)
    im.thumbnail((2400, 2400), Image.LANCZOS)
    steps["01_original"] = im.copy()

    if args.fit == "cover":
        if args.face_center:
            if debug_root:
                im = face_center_crop_debug(im, debug_root, src.stem)
            else:
                im = face_center_crop(im)
        else:
            im = cover_crop(im, args.anchor)
    else:
        im = contain_pad(im, args.anchor, args.bg, codes, C.lab_to_oklab(coords_lab))
    steps["02_fitted"] = im.copy()

    arr01 = np.asarray(im, dtype=np.float64) / 255.0
    if args.saturation != 1.0:
        arr01 = apply_saturation(arr01, args.saturation)
        im = Image.fromarray((arr01 * 255.0 + 0.5).astype(np.uint8))
    if args.sharpen > 0:
        from PIL import ImageFilter

        im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=args.sharpen, threshold=2))
        arr01 = np.asarray(im, dtype=np.float64) / 255.0
    steps["03_enhanced"] = im.copy()

    if args.space == "oklab":
        coords_img = C.srgb_to_oklab(arr01)
        steps["04_oklab_view"] = Image.fromarray(
            (np.clip(C.oklab_to_srgb01(coords_img), 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
        )
        if args.tone_map:
            coords_img = tone_map(coords_img, coords, args.tone_lo, args.tone_hi)
            steps["04b_tonemapped_view"] = Image.fromarray(
                (np.clip(C.oklab_to_srgb01(coords_img), 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
            )
    else:
        coords_img = C.srgb_to_lab(arr01)
        if args.tone_map:
            coords_img = tone_map(coords_img, coords, args.tone_lo, args.tone_hi)

    idx_hard = nearest_indices(coords_img, coords)
    steps["05_nearest_hard"] = pen_image(idx_hard, codes)

    idx = C.fs_dither(coords_img, coords, serpentine=not args.no_serpentine, clamp=args.clamp_error)
    steps["06_dithered_panel"] = pen_image(idx, codes)

    labs = np.array([p["lab"] for p in C.png_pens(doc)], dtype=float)[idx.ravel()]
    sim01 = np.clip(C.lab_to_srgb01(labs.reshape(480, 800, 3)), 0.0, 1.0)
    preview = Image.fromarray((sim01 * 255.0 + 0.5).astype(np.uint8))
    steps["07_preview_measured"] = preview

    src_lab = C.srgb_to_lab(arr01).reshape(-1, 3)
    dith_lab = labs.reshape(-1, 3)
    de_dither = C.delta_e_2000(src_lab, dith_lab)
    hard_lab = np.array([p["lab"] for p in C.png_pens(doc)], dtype=float)[idx_hard.ravel()]
    de_hard = C.delta_e_2000(src_lab, hard_lab)

    total = idx.size
    stats = {
        "hist_hard": histogram(idx_hard, names, total),
        "hist_dither": histogram(idx, names, total),
        "de_hard_mean": float(de_hard.mean()),
        "de_hard_p95": float(np.percentile(de_hard, 95)),
        "de_dither_mean": float(de_dither.mean()),
        "de_dither_p95": float(np.percentile(de_dither, 95)),
    }
    return steps, idx, stats


def main():
    ap = argparse.ArgumentParser(description="Prepare images for Inky Frame 7.3 (crop, scale, calibrate, Floyd–Steinberg)")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--outdir", default=".")
    ap.add_argument("--palette", default=None)
    ap.add_argument("--space", choices=["oklab", "cielab"], default="oklab")
    ap.add_argument("--fit", choices=["cover", "contain"], default="cover")
    ap.add_argument("--anchor", choices=list(ANCHORS), default="center")
    ap.add_argument("--face-center", action="store_true",
                    help="detect faces and vertically center the mean face position (cover mode only)")
    ap.add_argument("--bg", choices=["auto", "white", "black"], default="auto")
    ap.add_argument("--saturation", type=float, default=1.0,
                    help="pre-dither saturation boost (measured pigments are already muted; >1 raises gamut clipping)")
    ap.add_argument("--sharpen", type=int, default=0)
    ap.add_argument("--no-serpentine", action="store_true")
    ap.add_argument("--clamp-error", type=float, default=None)
    ap.add_argument("--no-tone-map", dest="tone_map", action="store_false",
                    help="disable dynamic-range remap onto panel gamut")
    ap.add_argument("--tone-map", dest="tone_map", action="store_true",
                    help="remap lightness onto panel range (darkens midtones; usually worse fidelity)")
    ap.add_argument("--tone-lo", type=float, default=0.5)
    ap.add_argument("--tone-hi", type=float, default=99.5)
    ap.set_defaults(tone_map=False)
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--debug-dir", default=None, help="write every intermediate step per image here")
    args = ap.parse_args()

    if args.face_center and not CV2_AVAILABLE:
        print("WARNING: --face-center requested but OpenCV not available; falling back to --anchor")
        args.face_center = False

    palette_path = Path(args.palette) if args.palette else (
        DEFAULT_PALETTE if DEFAULT_PALETTE.exists() else FALLBACK_PALETTE
    )
    doc = C.load_palette(palette_path)
    if not doc.get("measured"):
        print(f"NOTE: {palette_path.name} contains UNMEASURED estimates; run calibration/measure.py for real accuracy")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    debug_root = Path(args.debug_dir) if args.debug_dir else None
    if debug_root:
        debug_root.mkdir(parents=True, exist_ok=True)

    for path in args.inputs:
        src = Path(path)
        steps, idx, stats = process_image(src, doc, args, debug_root)

        print(f"{src.name}:")
        print("  quantization error (hard):   mean ΔE00 %.2f  p95 %.2f" % (stats["de_hard_mean"], stats["de_hard_p95"]))
        print("  quantization error (dither): mean ΔE00 %.2f  p95 %.2f" % (stats["de_dither_mean"], stats["de_dither_p95"]))
        for label, hist_key in (("nearest", "hist_hard"), ("dither ", "hist_dither")):
            parts = [f"{n} {p:5.1f}%" for n, _, p in stats[hist_key]]
            print(f"  {label}: " + " | ".join(parts))

        codes, *_ = C.pen_arrays(doc, space="cielab")
        flat_palette = []
        for code in codes:
            flat_palette += [int(code[0]), int(code[1]), int(code[2])]
        out = Image.new("P", (800, 480))
        out.putpalette(flat_palette)
        out.putdata(idx.astype(np.uint8).ravel().tolist())
        out_path = outdir / f"{src.stem}_inky.png"
        out.save(out_path, optimize=True)

        if args.preview or debug_root:
            steps["07_preview_measured"].save(outdir / f"{src.stem}_preview.png")

        if debug_root:
            d = debug_root / src.stem
            d.mkdir(parents=True, exist_ok=True)
            for name, im_step in steps.items():
                im_step.save(d / f"{name}.png")
            lines = [
                f"source: {src}",
                f"space: {args.space}  fit: {args.fit}/{args.anchor}  saturation: {args.saturation}  sharpen: {args.sharpen}",
                f"quantization error hard:   mean dE00 {stats['de_hard_mean']:.2f}  p95 {stats['de_hard_p95']:.2f}",
                f"quantization error dither: mean dE00 {stats['de_dither_mean']:.2f}  p95 {stats['de_dither_p95']:.2f}",
                "",
                "pen usage (hard nearest):",
            ]
            for n, cnt, pct in stats["hist_hard"]:
                lines.append(f"  {n:7s} {cnt:7d}  {pct:5.1f}%")
            lines.append("pen usage (floyd-steinberg):")
            for n, cnt, pct in stats["hist_dither"]:
                lines.append(f"  {n:7s} {cnt:7d}  {pct:5.1f}%")
            (d / "report.txt").write_text("\n".join(lines) + "\n")

        print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()
