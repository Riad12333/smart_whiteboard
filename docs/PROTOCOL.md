# Communication & Data Exchange Protocol (Step 4quinquies - Partie E)

> **Smart Interactive Whiteboard — USTHB (2026-2027)**  
> Technical protocol specification for decoupled system components, REST/WebSocket bridges, and future Web / Browser porting (without client-side framework lock-in).

---

## 1. Overview & Architecture Separation

To decouple the pure computer vision / mathematics engine from the presentation layer (Pygame, Web Canvas, React, or Electron), all communication adheres to strict, validated JSON schemas:

```
[ Camera Stream / Video Feed ]
             │
             ▼
[ Computer Vision Engine ]
  - Palm Detection + Handpose (cv2.dnn)
  - Color Segmentation (YCrCb / HSV)
  - 1€ Filter / EMA Deadzone
             │
             ▼ JSON Exchange
[ DLT Homography & Mapping ]
             │
             ▼ JSON Exchange (Pointer Data + Remote Events)
[ Interactive Canvas UI / Web Frontend ]
```

---

## 2. Pointer Exchange Schema

Every processed frame emits a pointer state dictionary:

```json
{
  "detected": true,
  "x": 320.45,
  "y": 241.12,
  "raw_x": 321.80,
  "raw_y": 243.50,
  "area": 14200,
  "u": 640.85,
  "v": 361.20,
  "score": 0.942,
  "pointing": true,
  "box": [220.0, 160.0, 420.0, 360.0],
  "landmarks": [
    [280.5, 340.2, 0.0],
    [290.1, 320.4, -0.01],
    [320.45, 241.12, -0.05]
  ],
  "inference_time_ms": 11.85
}
```

### Field Definitions:
- `detected` (`boolean`): Whether a hand or marker pointer is actively tracked.
- `x`, `y` (`float`): Camera pixel coordinates **after temporal stabilization** (1€ Filter / EMA and deadzone).
- `raw_x`, `raw_y` (`float`): Unfiltered, raw camera pixel coordinates directly from detector.
- `area` (`integer`): Estimated pixel area of the hand bounding box or colored blob.
- `u`, `v` (`float`): Projective whiteboard screen coordinates in pixels $[0, \text{BOARD\_WIDTH}] \times [0, \text{BOARD\_HEIGHT}]$.
- `score` (`float`): Real confidence score returned by the neural network $[0.0, 1.0]$.
- `pointing` (`boolean`): Whether the index-pointing gesture is validated.
- `box` (`[float, float, float, float]` or `null`): `[x1, y1, x2, y2]` bounding box in camera pixels.
- `landmarks` (`array` of 21 3D coordinates `[x, y, z]` or `null`): Full hand skeleton joints.
- `inference_time_ms` (`float`): Total frame processing latency in milliseconds.

When no pointer is found (`detected: false`):
```json
{
  "detected": false,
  "x": 0.0,
  "y": 0.0,
  "raw_x": 0.0,
  "raw_y": 0.0,
  "area": 0,
  "u": 0.0,
  "v": 0.0,
  "score": 0.0,
  "pointing": false,
  "box": null,
  "landmarks": null,
  "inference_time_ms": 10.5
}
```

---

## 3. Presentation Remote Control Event Schema

Presentation remotes or keyboard simulation emit discrete action events:

```json
{
  "event": "LEFT_CLICK",
  "timestamp": 1732578800.125,
  "source": "HID_KEYBOARD",
  "raw_keycode": 2555904
}
```

### Supported Events:
- `"LEFT_CLICK"`: Primary select, button activation, pen down/up toggle.
- `"RIGHT_CLICK"`: Menu return, cancellation, undo action.
- `null`: Idle state (no button press).

---

## 4. Drawing Stroke Schema (Vector Path)

Drawing paths are stored as vector stroke objects, compatible with SVG `<path>` and HTML5 Canvas `ctx.lineTo()`:

```json
{
  "id": "stroke_1732578800_1",
  "tool": "PEN",
  "color": [25, 113, 194],
  "thickness": 7,
  "points": [
    [100.5, 150.2],
    [105.0, 154.8],
    [112.3, 162.0],
    [125.1, 175.4]
  ]
}
```

### Supported Tools:
- `"PEN"`: Smooth round-brush Bresenham stroke rasterization.
- `"ERASER"`: Circular mask erasing stroke history.
- `"RECTANGLE"`, `"CIRCLE"`, `"LINE"`, `"ARROW"`: Geometric vector primitives.

---

## 5. Homography Calibration Fixtures (`tests/fixtures/homography_cases.json`)

To enable seamless porting to JavaScript / WebAssembly, projective DLT calculations are verified against reference test vectors:

```json
{
  "calibration_pairs": {
    "camera_src_corners": [[60.0, 40.0], [580.0, 40.0], [580.0, 440.0], [60.0, 440.0]],
    "board_dst_corners": [[0.0, 0.0], [1280.0, 0.0], [1280.0, 720.0], [0.0, 720.0]]
  },
  "expected_homography_matrix_3x3": [
    [2.46153846, 0.0, -147.69230769],
    [0.0, 1.8, -72.0],
    [0.0, 0.0, 1.0]
  ]
}
```

A JavaScript test runner (e.g. Jest / Mocha) can import this file and assert:
```javascript
const H = computeHomographyDLT(fixture.calibration_pairs.camera_src_corners, fixture.calibration_pairs.board_dst_corners);
expect(H).toBeCloseToMatrix(fixture.expected_homography_matrix_3x3);
```
