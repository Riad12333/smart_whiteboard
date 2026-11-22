# Smart Interactive Whiteboard — USTHB (2026-2027)

> **Computer Vision Project — Master Computer Science (USTHB)**  
> Camera-based interactive whiteboard operated via bare-hand pointing (or colored marker fallback) and a 2-button presentation remote.

---

## 🎨 Overview & Excalidraw UI

The interface is inspired by the minimalist, organic aesthetic of **Excalidraw**, optimized for distant pointing and high-contrast projector rendering:
- **Off-white canvas** with a subtle dot grid.
- **Floating pill top toolbar** (Accueil, Stylo, Gomme, Formes, Images, Leçons, Réglages).
- **Magnetic pointer snapping** (`SNAP_RADIUS = 75px`) to eliminate physiological hand jitter.
- **Vision-Safe Palette**: Strict prohibition of skin-like (orange/beige) and marker-like (green) tones in large GUI areas to prevent computer vision feedback loops. Available colors: Black (`#1e1e1e`), Blue (`#1971c2`), Red (`#e03131`), and Purple (`#6741d9`).
- **Visual Feedback**: 150ms click ripples and bottom contextual toast pills.

---

## 🏗️ Architecture

```
SMART_WHITEBOARD/
├── main.py                     # Main event loop & Technical Supervisor Dashboard
├── modules/
│   ├── camera.py               # Video capture & FPS calculation
│   ├── detection.py            # YCrCb color segmentation, morphology & CCL from scratch
│   ├── calibration.py          # Direct Linear Transform (DLT) 8x8 homography solver
│   ├── mapping.py              # Camera-to-board coordinate projection
│   ├── remote.py               # HID presentation remote debouncer & keycode mapper
│   ├── drawing.py              # Pure NumPy Bresenham rasterization & stroke history
│   ├── interface.py            # Excalidraw-styled Pygame whiteboard GUI
│   ├── interaction.py          # Action routing & magnetic snap coordination
│   └── features.py             # Image Zoom, CV Mini-Lesson & System Reset
├── config/
│   ├── settings.py             # Centralized application parameters
│   └── calibration_data.json   # Saved homography matrix & corners
├── assets/                     # Fonts (Patrick Hand), test video & lesson diagrams
├── tests/                      # Full test suite (29 unit & integration tests)
├── docs/                       # Project roadmap & milestones
├── requirements.txt            # Python dependencies
└── README.md
```

---

## 🚀 Quickstart

### 1. Requirements & Setup
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run Test Suite
```powershell
python -m unittest discover -s tests
```

### 3. Launch Application
```powershell
python main.py
```

### Shortcuts:
* `m`: Toggle Mouse Simulation mode $\longleftrightarrow$ Camera mode.
* `d`: Toggle Technical Supervisor Dashboard (Camera telemetry HUD).
* `f`: Toggle Fullscreen.
* `c`: Recalibrate skin color ROI on live video.
* `q` / `ESC`: Exit.

---

## 📐 Implemented Algorithms (From Scratch)
* **Color Space Conversion**: Pure NumPy $BGR \to YCrCb$ (ITU-R BT.601) and $BGR \to HSV$.
* **Mathematical Morphology**: Flat $3 \times 3$ erosion, dilation, and opening.
* **Connected Component Labeling (CCL)**: Decimated BFS connected components to isolate largest blob.
* **Fingertip Extraction**: Farthest contour point from centroid ($\max d^2$).
* **Temporal Smoothing**: Exponential Moving Average (EMA) + deadzone jitter filter.
* **DLT Homography**: 8-equation linear system solved via Direct Linear Transformation (`np.linalg.solve`).
* **Line Rasterization**: Integer Bresenham line algorithm with round brush stamping.
