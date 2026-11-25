"""
Configuration module for Smart Interactive Whiteboard.
Loads parameters from 'config/settings.json' and exposes them as typed module-level constants.
Ensures 100% backward compatibility with all existing application modules and tests.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

# Base paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_JSON_PATH = PROJECT_ROOT / "config" / "settings.json"


def load_settings_dict() -> Dict[str, Any]:
    """Load settings dictionary from config/settings.json if present."""
    if os.path.exists(SETTINGS_JSON_PATH):
        try:
            with open(SETTINGS_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Settings] Warning: Failed to parse settings.json ({e}). Using default fallbacks.")
    return {}


_cfg = load_settings_dict()

# ==============================================================================
# Camera and Acquisition Settings
# ==============================================================================
_cam = _cfg.get("camera", {})
CAMERA_SOURCE: Union[int, str] = _cam.get("camera_source", 0)
FRAME_WIDTH: int = int(_cam.get("frame_width", 640))
FRAME_HEIGHT: int = int(_cam.get("frame_height", 480))
FPS_TARGET: int = int(_cam.get("fps_target", 60))
FPS_CALC_WINDOW: int = int(_cam.get("fps_calc_window", 15))
VIDEO_TEST_PATH: str = str(_cam.get("video_test_path", "assets/test_video.avi"))
RECORD_DURATION_SEC: int = int(_cam.get("record_duration_sec", 5))
RECORD_FOURCC: str = str(_cam.get("record_fourcc", "XVID"))

# ==============================================================================
# Board and Projection Dimensions (in pixels)
# ==============================================================================
_brd = _cfg.get("board", {})
BOARD_WIDTH: int = int(_brd.get("board_width", 1280))
BOARD_HEIGHT: int = int(_brd.get("board_height", 720))
UI_FULLSCREEN_DEFAULT: bool = bool(_brd.get("ui_fullscreen_default", False))
DASHBOARD_ENABLED_DEFAULT: bool = bool(_brd.get("dashboard_enabled_default", False))
MAIN_WINDOW_NAME: str = str(_brd.get("main_window_name", "Smart Interactive Whiteboard (Projected Surface)"))
DASHBOARD_WINDOW_NAME: str = str(_brd.get("dashboard_window_name", "Technical Supervisor Dashboard (Camera & Telemetry)"))

# ==============================================================================
# Excalidraw-Inspired Design Palette (RGB tuples for Pygame)
# ==============================================================================
_pal = _cfg.get("palette", {})
EXCALI_BG: Tuple[int, int, int] = tuple(_pal.get("excali_bg", [251, 251, 252]))
EXCALI_GRID_DOT: Tuple[int, int, int] = tuple(_pal.get("excali_grid_dot", [218, 222, 229]))
EXCALI_CARD_BG: Tuple[int, int, int] = tuple(_pal.get("excali_card_bg", [255, 255, 255]))
EXCALI_CARD_BORDER: Tuple[int, int, int] = tuple(_pal.get("excali_card_border", [40, 40, 40]))
DRAWING_BG_COLOR: Tuple[int, int, int] = EXCALI_BG

EXCALI_PURPLE: Tuple[int, int, int] = tuple(_pal.get("excali_purple", [105, 101, 219]))
EXCALI_PURPLE_DARK: Tuple[int, int, int] = tuple(_pal.get("excali_purple_dark", [92, 86, 223]))
EXCALI_PURPLE_LIGHT: Tuple[int, int, int] = tuple(_pal.get("excali_purple_light", [238, 237, 254]))
EXCALI_BLUE: Tuple[int, int, int] = tuple(_pal.get("excali_blue", [25, 113, 194]))

COLOR_DRAW_BLACK: Tuple[int, int, int] = tuple(_pal.get("color_draw_black", [30, 30, 30]))
COLOR_DRAW_BLUE: Tuple[int, int, int] = tuple(_pal.get("color_draw_blue", [25, 113, 194]))
COLOR_DRAW_RED: Tuple[int, int, int] = tuple(_pal.get("color_draw_red", [224, 49, 49]))
COLOR_DRAW_PURPLE: Tuple[int, int, int] = tuple(_pal.get("color_draw_purple", [103, 65, 217]))

EXCALI_TEXT_MAIN: Tuple[int, int, int] = tuple(_pal.get("excali_text_main", [30, 30, 30]))
EXCALI_TEXT_MUTED: Tuple[int, int, int] = tuple(_pal.get("excali_text_muted", [115, 115, 125]))

# Pen Thickness Options
_pen = _cfg.get("pen_thickness", {})
PEN_THIN_THICKNESS: int = int(_pen.get("thin", 3))
PEN_MEDIUM_THICKNESS: int = int(_pen.get("medium", 7))
PEN_THICK_THICKNESS: int = int(_pen.get("thick", 14))
ERASER_THICKNESS: int = int(_pen.get("eraser", 35))

# ==============================================================================
# Interaction, Magnetic Snapping & Animation
# ==============================================================================
_act = _cfg.get("interaction", {})
SNAP_RADIUS: float = float(_act.get("snap_radius", 75.0))
HOVER_SCALE: float = float(_act.get("hover_scale", 1.08))
ANIMATION_DURATION_MS: int = int(_act.get("animation_duration_ms", 150))
FONT_HANDWRITTEN: str = str(_act.get("font_handwritten", "assets/fonts/PatrickHand-Regular.ttf"))

# ==============================================================================
# Geometric Calibration & Homography Mapping (Step 5)
# ==============================================================================
_cal = _cfg.get("calibration", {})
CALIBRATION_DATA_PATH: str = str(_cal.get("calibration_data_path", "config/calibration_data.json"))
DEFAULT_CAMERA_CORNERS: List[List[float]] = _cal.get(
    "default_camera_corners", [[60.0, 40.0], [580.0, 40.0], [580.0, 440.0], [60.0, 440.0]]
)
VALIDATION_BOARD_POINTS: List[List[float]] = _cal.get(
    "validation_board_points",
    [[640.0, 360.0], [320.0, 180.0], [960.0, 180.0], [320.0, 540.0], [960.0, 540.0]]
)

# ==============================================================================
# Pointer Detection & Color Segmentation Settings
# ==============================================================================
_d_skin = _cfg.get("detection_skin", {})
SKIN_CR_MIN: int = int(_d_skin.get("skin_cr_min", 133))
SKIN_CR_MAX: int = int(_d_skin.get("skin_cr_max", 173))
SKIN_CB_MIN: int = int(_d_skin.get("skin_cb_min", 77))
SKIN_CB_MAX: int = int(_d_skin.get("skin_cb_max", 127))
CALIB_ROI_SIZE: int = int(_d_skin.get("calib_roi_size", 60))
CALIB_K_STD: float = float(_d_skin.get("calib_k_std", 2.0))
MORPH_ITERATIONS: int = int(_d_skin.get("morph_iterations", 1))
CCL_DOWNSCALE: int = int(_d_skin.get("ccl_downscale", 4))
MIN_CONTOUR_AREA: int = int(_d_skin.get("min_contour_area", 500))
FINGERTIP_METHOD: str = str(_d_skin.get("fingertip_method", "FARTHEST"))

_d_marker = _cfg.get("detection_marker", {})
MARKER_H_MIN: int = int(_d_marker.get("marker_h_min", 35))
MARKER_H_MAX: int = int(_d_marker.get("marker_h_max", 85))
MARKER_S_MIN: int = int(_d_marker.get("marker_s_min", 80))
MARKER_S_MAX: int = int(_d_marker.get("marker_s_max", 255))
MARKER_V_MIN: int = int(_d_marker.get("marker_v_min", 60))
MARKER_V_MAX: int = int(_d_marker.get("marker_v_max", 255))

_stb = _cfg.get("stabilization", {})
SMOOTHING_ALPHA: float = float(_stb.get("smoothing_alpha", 0.35))
DEADZONE_RADIUS: float = float(_stb.get("deadzone_radius", 3.5))
MAX_LOST_FRAMES: int = int(_stb.get("max_lost_frames", 5))
DETECTION_MODE_DEFAULT: str = str(_stb.get("detection_mode_default", "SKIN"))

# ==============================================================================
# Machine Learning Hand Detection Settings (Step 4quinquies - OpenCV Zoo DNN)
# ==============================================================================
_dml = _cfg.get("detection_ml", {})
HAND_ML_PALM_MODEL_PATH: str = str(_dml.get("palm_model_path", "assets/models/palm_detection_mediapipe_2023feb.onnx"))
HAND_ML_HAND_MODEL_PATH: str = str(_dml.get("hand_model_path", "assets/models/handpose_estimation_mediapipe_2023feb.onnx"))
HAND_ML_PALM_SCORE_THRESH: float = float(_dml.get("palm_score_thresh", 0.6))
HAND_ML_HAND_SCORE_THRESH: float = float(_dml.get("hand_score_thresh", 0.7))
HAND_ML_NMS_THRESH: float = float(_dml.get("nms_thresh", 0.3))
HAND_ML_REQUIRE_POINTING: bool = bool(_dml.get("require_pointing", False))
HAND_ML_DETECT_EVERY_N: int = int(_dml.get("detect_every_n", 1))
HAND_ML_DOWNSCALE_FACTOR: float = float(_dml.get("downscale_factor", 1.0))
HAND_ML_BOARD_MARGIN: float = float(_dml.get("board_margin", 30.0))
HAND_ML_FILTER_TYPE: str = str(_dml.get("filter_type", "ONE_EURO"))
HAND_ML_ONE_EURO_MIN_CUTOFF: float = float(_dml.get("one_euro_min_cutoff", 1.0))
HAND_ML_ONE_EURO_BETA: float = float(_dml.get("one_euro_beta", 0.007))
HAND_ML_ONE_EURO_D_CUTOFF: float = float(_dml.get("one_euro_d_cutoff", 1.0))

# ==============================================================================
# Remote Control Key Mappings
# ==============================================================================
_rem = _cfg.get("remote", {})
REMOTE_DEBOUNCE_SEC: float = float(_rem.get("debounce_sec", 0.25))
REMOTE_NEXT_KEYCODES: List[int] = _rem.get(
    "next_keycodes", [2555904, 83, 2228224, 86, ord("n"), ord("N"), ord("d"), ord("D"), 32]
)
REMOTE_PREV_KEYCODES: List[int] = _rem.get(
    "prev_keycodes", [2424832, 2490368, 81, 2162688, 85, ord("p"), ord("P"), ord("g"), ord("G"), 8]
)

# ==============================================================================
# Free Functionalities Settings
# ==============================================================================
_feat = _cfg.get("features", {})
DEFAULT_LESSON_IMAGE: str = str(_feat.get("default_lesson_image", "assets/lesson_diagram.png"))
ZOOM_MIN: float = float(_feat.get("zoom_min", 0.5))
ZOOM_MAX: float = float(_feat.get("zoom_max", 3.5))
ZOOM_STEP: float = float(_feat.get("zoom_step", 0.3))

# ==============================================================================
# Visual Settings & Colors (BGR format for OpenCV debug windows)
# ==============================================================================
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_RED = (0, 0, 255)
COLOR_GREEN = (0, 255, 0)
COLOR_BLUE = (255, 0, 0)
COLOR_YELLOW = (0, 255, 255)
COLOR_CYAN = (255, 255, 0)
COLOR_MAGENTA = (255, 0, 255)
COLOR_GRAY = (128, 128, 128)
COLOR_DARK_GRAY = (35, 35, 35)
COLOR_LIGHT_GRAY = (220, 220, 220)
COLOR_PANEL_BG = (42, 42, 42)
COLOR_BUTTON_NORMAL = (65, 65, 65)
COLOR_BUTTON_HOVER = (100, 100, 100)
COLOR_BUTTON_ACTIVE = (0, 150, 255)

# Application Info
_app = _cfg.get("app", {})
APP_NAME: str = str(_app.get("name", "Smart Interactive Whiteboard (USTHB 2026-2027)"))
APP_VERSION: str = str(_app.get("version", "2.0.0"))
