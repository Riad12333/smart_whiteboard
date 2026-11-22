"""
Configuration file for Smart Interactive Whiteboard.
All adjustable parameters must be defined here, never hardcoded in modules.
"""

from typing import List, Tuple, Union

# ==============================================================================
# Camera and Acquisition Settings
# ==============================================================================
CAMERA_SOURCE: Union[int, str] = 0

FRAME_WIDTH: int = 640
FRAME_HEIGHT: int = 480
FPS_TARGET: int = 60
FPS_CALC_WINDOW: int = 15
VIDEO_TEST_PATH: str = "assets/test_video.avi"
RECORD_DURATION_SEC: int = 5
RECORD_FOURCC: str = "XVID"

# ==============================================================================
# Board and Projection Dimensions (in pixels)
# ==============================================================================
BOARD_WIDTH: int = 1280
BOARD_HEIGHT: int = 720
UI_FULLSCREEN_DEFAULT: bool = False
DASHBOARD_ENABLED_DEFAULT: bool = False  # Keep off by default for clean Excalidraw view

MAIN_WINDOW_NAME: str = "Smart Interactive Whiteboard (Projected Surface)"
DASHBOARD_WINDOW_NAME: str = "Technical Supervisor Dashboard (Camera & Telemetry)"

# ==============================================================================
# Excalidraw-Inspired Design Palette (RGB tuples for Pygame)
# ==============================================================================
# Canvas & Background
EXCALI_BG: Tuple[int, int, int] = (251, 251, 252)             # Crisp off-white
EXCALI_GRID_DOT: Tuple[int, int, int] = (218, 222, 229)       # Subtle grid dot
EXCALI_CARD_BG: Tuple[int, int, int] = (255, 255, 255)        # Pure white pill/card
EXCALI_CARD_BORDER: Tuple[int, int, int] = (40, 40, 40)       # Hand-drawn black stroke
DRAWING_BG_COLOR: Tuple[int, int, int] = EXCALI_BG

# Accent Colors
EXCALI_PURPLE: Tuple[int, int, int] = (105, 101, 219)         # Excalidraw Accent #6965db
EXCALI_PURPLE_DARK: Tuple[int, int, int] = (92, 86, 223)      # Active / Clicked #5c56df
EXCALI_PURPLE_LIGHT: Tuple[int, int, int] = (238, 237, 254)   # Selected highlight #eeedfe
EXCALI_BLUE: Tuple[int, int, int] = (25, 113, 194)            # Excalidraw Blue #1971c2

# Safe 4 Drawing Colors (Zero green or skin tone to prevent camera confusion)
COLOR_DRAW_BLACK: Tuple[int, int, int] = (30, 30, 30)         # #1e1e1e
COLOR_DRAW_BLUE: Tuple[int, int, int] = (25, 113, 194)        # #1971c2
COLOR_DRAW_RED: Tuple[int, int, int] = (224, 49, 49)          # #e03131
COLOR_DRAW_PURPLE: Tuple[int, int, int] = (103, 65, 217)      # #6741d9

# Text Colors
EXCALI_TEXT_MAIN: Tuple[int, int, int] = (30, 30, 30)
EXCALI_TEXT_MUTED: Tuple[int, int, int] = (115, 115, 125)

# Pen Thickness Options
PEN_THIN_THICKNESS: int = 3
PEN_MEDIUM_THICKNESS: int = 7
PEN_THICK_THICKNESS: int = 14
ERASER_THICKNESS: int = 35

# ==============================================================================
# Interaction, Magnetic Snapping & Animation
# ==============================================================================
SNAP_RADIUS: float = 75.0             # Distance in px within which cursor snaps to button
HOVER_SCALE: float = 1.08             # Scale expansion on hover
ANIMATION_DURATION_MS: int = 150      # Duration of click ripple and hover transitions
FONT_HANDWRITTEN: str = "assets/fonts/PatrickHand-Regular.ttf"

# ==============================================================================
# Geometric Calibration & Homography Mapping (Step 5)
# ==============================================================================
CALIBRATION_DATA_PATH: str = "config/calibration_data.json"

DEFAULT_CAMERA_CORNERS = [
    [60.0, 40.0],
    [580.0, 40.0],
    [580.0, 440.0],
    [60.0, 440.0]
]

VALIDATION_BOARD_POINTS = [
    [640.0, 360.0],
    [320.0, 180.0],
    [960.0, 180.0],
    [320.0, 540.0],
    [960.0, 540.0]
]

# ==============================================================================
# Pointer Detection & Color Segmentation Settings
# ==============================================================================
SKIN_CR_MIN: int = 133
SKIN_CR_MAX: int = 173
SKIN_CB_MIN: int = 77
SKIN_CB_MAX: int = 127

CALIB_ROI_SIZE: int = 60
CALIB_K_STD: float = 2.0

MORPH_ITERATIONS: int = 1
CCL_DOWNSCALE: int = 4
MIN_CONTOUR_AREA: int = 500
FINGERTIP_METHOD: str = "FARTHEST"

SMOOTHING_ALPHA: float = 0.35
DEADZONE_RADIUS: float = 3.5
MAX_LOST_FRAMES: int = 5
DETECTION_MODE_DEFAULT: str = "SKIN"

MARKER_H_MIN: int = 35
MARKER_H_MAX: int = 85
MARKER_S_MIN: int = 80
MARKER_S_MAX: int = 255
MARKER_V_MIN: int = 60
MARKER_V_MAX: int = 255

# ==============================================================================
# Remote Control Key Mappings
# ==============================================================================
REMOTE_DEBOUNCE_SEC: float = 0.25

REMOTE_NEXT_KEYCODES: List[int] = [
    2555904, 83, 2228224, 86, ord("n"), ord("N"), ord("d"), ord("D"), 32,
]

REMOTE_PREV_KEYCODES: List[int] = [
    2424832, 2490368, 81, 2162688, 85, ord("p"), ord("P"), ord("g"), ord("G"), 8,
]

# ==============================================================================
# Free Functionalities Settings
# ==============================================================================
DEFAULT_LESSON_IMAGE: str = "assets/lesson_diagram.png"
ZOOM_MIN: float = 0.5
ZOOM_MAX: float = 3.5
ZOOM_STEP: float = 0.3

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
APP_NAME: str = "Smart Interactive Whiteboard (USTHB 2026-2027)"
APP_VERSION: str = "2.0.0"
