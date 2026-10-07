# InkyFrame 7.3 Gallery - Image Display Pipeline

This repository contains the minimal code needed to display images on the Pimoroni Inky Frame 7.3" Gallery (7-color e-ink) display.

## Repository Structure

```
inkyframe/
├── process.py              # Host image processing pipeline
├── palettes/
│   └── inky73_measured.json  # Measured 7-color palette
├── micropython/            # Device firmware (copy to InkyFrame)
│   ├── calibrate.py        # Display calibration charts on device
│   ├── inky_layout.py      # Chart layout definitions (4x2 grid + 13-step grey ramp)
│   ├── main.py             # Main device application
│   ├── viewer.py           # Image viewer
│   └── main_reference.py   # Reference implementation
├── palettes/
│   └── inky73_measured.json  # 7-color measured palette
└── .gitignore
```

---

## Micropython Files (Device Firmware)

Copy the `micropython/` folder contents to your InkyFrame 7.3" Gallery device.

### Files:
- **`calibrate.py`** - Displays calibration charts on the device. Shows Chart A and Chart B (each 4×2 grid of color patches) with a 13-step dithered grey ramp at the bottom. Press button B to advance between charts.
- **`inky_layout.py`** - Defines the chart geometry (800×480, 4×2 grid, 13-step grey ramp).
- **`main.py`** - Main application entry point.
- **`viewer.py`** - Image viewer for displaying processed images.
- **`main_reference.py`** - Reference implementation.

### Usage on Device:
1. Copy all `.py` files from `micropython/` to the root of your InkyFrame's filesystem.
2. Run `calibrate.py` to display calibration charts (place device on scanner for each chart).
3. Run `main.py` or `viewer.py` to display processed images.

---

## Host Image Processing (`process.py`)

Processes images on your computer for display on the InkyFrame.

### Requirements
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pillow opencv-python-headless numpy
```
**Note:** Use `opencv-python-headless<5` (version 4.x) - OpenCV 5 removed `CascadeClassifier`.

### Usage
```bash
# Basic usage (cover crop, center anchor)
python process.py image.jpg -o output_dir --palette palettes/inky73_measured.json

# Cover crop with face-centering (detects faces, centers vertically)
python process.py image.jpg -o output_dir --palette palettes/inky73_measured.json --face-center

# Contain mode (fit entire image, pad with background)
python process.py image.jpg -o output_dir --palette palettes/inky73_measured.json --fit contain --bg white

# Options
--space oklab          # Color space for dithering (default: oklab)
--fit cover|contain    # Cover crops to fill, contain pads (default: cover)
--anchor center|top|bottom|left|right  # Anchor for cover/contain (default: center)
--face-center          # Detect faces, vertically center mean face position (cover mode only)
--bg auto|white|black  # Background color for contain mode (default: auto)
--saturation N         # Pre-dither saturation boost (default: 1.0)
--sharpen N            # Unsharp mask radius (default: 0)
--no-serpentine        # Disable serpentine Floyd-Steinberg
--tone-map             # Remap lightness onto panel gamut
--preview              # Save preview images
--debug-dir DIR        # Save intermediate steps
```

### Output
- `image_inky.png` - 800×480 indexed PNG with 7-color palette (ready for device)
- `image_preview.png` - RGB preview of dithered result (if `--preview`)
- `debug/` - Intermediate steps (if `--debug-dir`)

### Face Centering (`--face-center`)
- Detects human faces (and cat faces) using OpenCV Haar cascades
- Computes mean vertical center of all detected faces
- Vertically pans the crop so mean face center aligns with display center (240px)
- Maintains full-width crop (800px), only vertical panning
- Clamps to valid range (no black bars)
- Falls back to `--anchor center` if no faces detected
- Works with `--fit cover` only (default)

### Palette
The measured palette `palettes/inky73_measured.json` contains 7 Lab colors:
- Black, White, Green, Blue, Red, Yellow, Orange
- Measured using IT8 target + scanner profiling with face-centering for accurate color reproduction

---

## Quick Start

```bash
# 1. Set up environment
python3 -m venv .venv
source .venv/bin/activate
pip install pillow opencv-python-headless==4.14.0.94 numpy

# 2. Process an image
python process.py my_photo.jpg -o output --palette palettes/inky73_measured.json --face-center --preview

# 3. Copy output/photo_inky.png to InkyFrame and display with viewer.py
```