/**
 * Settings loader for Smart Interactive Whiteboard (Web Version).
 * Attempts to fetch 'config/settings.json', falling back to bundled defaults
 * if running offline or under file:// protocol.
 */

export const DEFAULT_SETTINGS = {
  camera: {
    camera_source: 0,
    frame_width: 640,
    frame_height: 480,
    fps_target: 60,
    fps_calc_window: 15,
    mirror: true,
    edge_margin_pct: 0.08,
  },
  board: {
    board_width: 1280,
    board_height: 720,
    ui_fullscreen_default: false,
    dashboard_enabled_default: false,
    main_window_name: "Smart Interactive Whiteboard (Projected Surface)",
    dashboard_window_name: "Technical Supervisor Dashboard (Camera & Telemetry)"
  },
  palette: {
    excali_bg: [251, 251, 252],
    excali_grid_dot: [218, 222, 229],
    excali_card_bg: [255, 255, 255],
    excali_card_border: [40, 40, 40],
    excali_purple: [105, 101, 219],
    excali_purple_dark: [92, 86, 223],
    excali_purple_light: [238, 237, 254],
    excali_blue: [25, 113, 194],
    color_draw_black: [30, 30, 30],
    color_draw_blue: [25, 113, 194],
    color_draw_red: [224, 49, 49],
    color_draw_purple: [103, 65, 217],
    excali_text_main: [30, 30, 30],
    excali_text_muted: [115, 115, 125]
  },
  pen_thickness: {
    thin: 3,
    medium: 7,
    thick: 14,
    eraser: 35
  },
  interaction: {
    snap_radius: 75.0,
    magnet_radius_px: 75.0,
    hover_scale: 1.08,
    animation_duration_ms: 150
  },
  calibration: {
    default_camera_corners: [
      [60.0, 40.0],
      [580.0, 40.0],
      [580.0, 440.0],
      [60.0, 440.0]
    ],
    validation_board_points: [
      [640.0, 360.0],
      [320.0, 180.0],
      [960.0, 180.0],
      [320.0, 540.0],
      [960.0, 540.0]
    ]
  },
  detection_ml: {
    palm_score_thresh: 0.6,
    hand_score_thresh: 0.7,
    require_pointing: false,
    board_margin: 30.0,
    filter_type: "ONE_EURO",
    one_euro_min_cutoff: 1.0,
    one_euro_beta: 0.007,
    one_euro_d_cutoff: 1.0
  },
  stabilization: {
    smoothing_alpha: 0.35,
    deadzone_radius: 3.5,
    max_lost_frames: 5,
    detection_mode_default: "MOUSE"
  },
  remote: {
    debounce_sec: 0.25,
    next_keys: ["PageDown", "ArrowRight", "n", "N", "d", "D", " "],
    prev_keys: ["PageUp", "ArrowLeft", "p", "P", "g", "G", "Backspace"]
  }
};

let activeSettings = { ...DEFAULT_SETTINGS };

/**
 * Asynchronously fetch settings from JSON, merging with defaults.
 */
export async function loadSettings(jsonUrl = "config/settings.json") {
  try {
    const res = await fetch(jsonUrl);
    if (res.ok) {
      const data = await res.json();
      activeSettings = { ...DEFAULT_SETTINGS, ...data };
      console.log("[Settings] Loaded settings from JSON successfully.");
    }
  } catch (err) {
    console.warn("[Settings] Using bundled default settings (fetch failed or file:// mode):", err.message);
  }
  return activeSettings;
}

export function getSettings() {
  return activeSettings;
}
