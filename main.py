"""
SMART INTERACTIVE WHITEBOARD — Main Application Entry Point (Step 10 & Step 4quinquies).
Integrates:
  - Video acquisition (Camera / IP Phone / Test Video)
  - Hand pointer detection (HAND_ML via OpenCV Zoo DNN, MARKER HSV, SKIN YCrCb)
  - DLT geometric camera-to-board homography mapping
  - Presentation remote event listening & debouncing
  - Fullscreen whiteboard interactive GUI (Drawing, Lesson, Zoom, Reset)
  - Real-time Technical Supervisor Dashboard with live 21-landmarks telemetry
  - Robust fault-tolerant error management
Part of the Smart Interactive Whiteboard project (USTHB 2026-2027).
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from config import settings
from modules.camera import CameraManager
from modules.detection import SkinColorCalibrator, PointerStabilizer, detect_pointer
from modules.detection_ml import HandMLDetector
from modules.calibration import BoardCalibrator
from modules.mapping import CoordinateMapper
from modules.remote import RemoteHandler
from modules.interface import WhiteboardInterface
from modules.interaction import InteractionManager


# MediaPipe 21 Hand Landmarks bone topology
HAND_CONNECTIONS = [
    # Thumb
    (0, 1), (1, 2), (2, 3), (3, 4),
    # Index finger
    (0, 5), (5, 6), (6, 7), (7, 8),
    # Middle finger
    (5, 9), (9, 10), (10, 11), (11, 12),
    # Ring finger
    (9, 13), (13, 14), (14, 15), (15, 16),
    # Pinky finger
    (13, 17), (17, 18), (18, 19), (19, 20),
    # Palm base connection
    (0, 17)
]


class TechnicalDashboard:
    """
    Renders a dedicated technical supervision HUD overlaying the live camera feed:
      - 21-landmarks skeleton and index pointer overlay (HAND_ML mode)
      - Raw & stabilized tracking crosshairs (MARKER / SKIN modes)
      - Calibrated whiteboard boundary polygon
      - Real-time FPS, inference time (ms), and model confidence score
      - Active HID presentation remote keycodes and click feedback
    """

    def __init__(self, width: int = 640, height: int = 480):
        self.width = width
        self.height = height

    def render(
        self,
        camera_frame: Optional[np.ndarray],
        pointer_data: Dict[str, Union[bool, float, int]],
        calibrator: BoardCalibrator,
        skin_calibrator: SkinColorCalibrator,
        stabilizer: PointerStabilizer,
        remote_handler: RemoteHandler,
        camera_fps: float,
        system_fps: float,
        mode: str,
        mouse_mode: bool,
    ) -> np.ndarray:
        if camera_frame is not None:
            hud_frame = camera_frame.copy()
        else:
            hud_frame = np.full((self.height, self.width, 3), 30, dtype=np.uint8)
            cv2.putText(
                hud_frame,
                "PAS DE CAMERA DETECTEE",
                (120, 240),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                settings.COLOR_RED,
                2,
            )

        # 1. Draw calibrated whiteboard boundary polygon if available
        if calibrator.is_calibrated and len(calibrator.src_corners) == 4:
            pts = np.array(calibrator.src_corners, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(hud_frame, [pts], isClosed=True, color=settings.COLOR_GREEN, thickness=2)
            cv2.putText(
                hud_frame,
                "ZONE TABLEAU",
                (int(calibrator.src_corners[0][0]) + 8, int(calibrator.src_corners[0][1]) + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                settings.COLOR_GREEN,
                1,
                cv2.LINE_AA,
            )

        # 2. Draw skin calibration target ROI (only in SKIN mode)
        roi_size = settings.CALIB_ROI_SIZE
        rx = (settings.FRAME_WIDTH - roi_size) // 2
        ry = (settings.FRAME_HEIGHT - roi_size) // 2
        if not skin_calibrator.is_calibrated and mode == "SKIN":
            cv2.rectangle(hud_frame, (rx, ry), (rx + roi_size, ry + roi_size), settings.COLOR_CYAN, 1)

        # 3. Draw tracking overlays
        if pointer_data.get("detected", False):
            # A) If 21 landmarks are available (HAND_ML mode)
            landmarks = pointer_data.get("landmarks")
            if landmarks is not None and len(landmarks) == 21:
                # Draw skeleton bones
                for p1_idx, p2_idx in HAND_CONNECTIONS:
                    pt1 = (int(landmarks[p1_idx, 0]), int(landmarks[p1_idx, 1]))
                    pt2 = (int(landmarks[p2_idx, 0]), int(landmarks[p2_idx, 1]))
                    cv2.line(hud_frame, pt1, pt2, (255, 200, 100), 2, cv2.LINE_AA)

                # Draw landmark joints
                for idx in range(21):
                    px, py = int(landmarks[idx, 0]), int(landmarks[idx, 1])
                    if idx == 8:
                        # Landmark 8: Index Fingertip (active pointer)
                        cv2.circle(hud_frame, (px, py), 7, settings.COLOR_RED, -1)
                        cv2.circle(hud_frame, (px, py), 14, settings.COLOR_YELLOW, 2)
                        cv2.drawMarker(hud_frame, (px, py), settings.COLOR_GREEN, cv2.MARKER_CROSS, 20, 2)
                        cv2.putText(hud_frame, "L8 (Index)", (px + 12, py - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, settings.COLOR_YELLOW, 1, cv2.LINE_AA)
                    else:
                        cv2.circle(hud_frame, (px, py), 3, (255, 255, 255), -1)
                        cv2.circle(hud_frame, (px, py), 4, (40, 180, 255), 1)

                # Draw hand bounding box
                box = pointer_data.get("box")
                if box is not None and len(box) == 4:
                    bx1, by1, bx2, by2 = map(int, box)
                    cv2.rectangle(hud_frame, (bx1, by1), (bx2, by2), (255, 120, 0), 1)

            else:
                # B) MARKER or SKIN mode: Centroid and Fingertip overlays
                if "cx" in pointer_data and "cy" in pointer_data:
                    cx, cy = int(pointer_data["cx"]), int(pointer_data["cy"])
                    cv2.circle(hud_frame, (cx, cy), 5, settings.COLOR_BLUE, -1)

                raw_x, raw_y = int(pointer_data.get("raw_x", 0)), int(pointer_data.get("raw_y", 0))
                cv2.circle(hud_frame, (raw_x, raw_y), 5, settings.COLOR_GRAY, 1)

                sx, sy = int(pointer_data.get("x", 0)), int(pointer_data.get("y", 0))
                cv2.circle(hud_frame, (sx, sy), 7, settings.COLOR_RED, -1)
                cv2.circle(hud_frame, (sx, sy), 15, settings.COLOR_GREEN, 2)
                cv2.drawMarker(hud_frame, (sx, sy), settings.COLOR_YELLOW, cv2.MARKER_CROSS, 20, 2)

        # 4. Telemetry overlay panel (Top Banner)
        cv2.rectangle(hud_frame, (5, 5), (self.width - 5, 85), (0, 0, 0), -1)
        cv2.rectangle(hud_frame, (5, 5), (self.width - 5, 85), settings.COLOR_LIGHT_GRAY, 1)

        det_status = "DETECTE" if pointer_data.get("detected") else "RECHERCHE..."
        det_col = settings.COLOR_GREEN if pointer_data.get("detected") else settings.COLOR_RED

        calib_err = calibrator.last_metrics.get("mean_validation_error_px", 0.0)
        calib_str = f"OK (Err: {calib_err:.2f}px)" if calibrator.is_calibrated else "DEFAUT"

        # Mode line
        active_mode_str = "SOURIS" if mouse_mode else mode
        inf_ms = pointer_data.get("inference_time_ms", 0.0)
        cv2.putText(
            hud_frame,
            f"Cam FPS: {camera_fps:4.1f} | Loop FPS: {system_fps:4.1f} | Mode: {active_mode_str} | Inf: {inf_ms:4.1f}ms",
            (15, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            settings.COLOR_YELLOW,
            1,
            cv2.LINE_AA,
        )

        # Tracking status line & Score
        score = float(pointer_data.get("score", 0.0))
        if mode == "HAND_ML":
            pointing_str = " [POINTAGE]" if pointer_data.get("pointing") else " [MAIN LIBRE]"
            tracking_info = f"{det_status}{pointing_str} | Conf: {score:.2f}"
        else:
            tracking_info = f"{det_status} | Calib DLT: {calib_str}"

        cv2.putText(
            hud_frame,
            f"Tracking: {tracking_info}",
            (15, 48),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            det_col,
            1,
            cv2.LINE_AA,
        )

        # Remote and stabilization line
        last_evt = remote_handler.get_last_event() or "Aucun"
        if mode == "HAND_ML":
            filter_name = getattr(settings, "HAND_ML_FILTER_TYPE", "ONE_EURO")
            sub_info = f"Filtre: {filter_name} | Calib DLT: {calib_str}"
        else:
            metrics = stabilizer.get_stability_metrics()
            sub_info = f"Jitter Reduc: -{metrics['jitter_reduction_pct']:.0f}%"

        cv2.putText(
            hud_frame,
            f"Dernier Clic: {last_evt} | {sub_info}",
            (15, 71),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            settings.COLOR_WHITE,
            1,
            cv2.LINE_AA,
        )

        # 5. Bottom banner: Real-time Coordinates
        cv2.rectangle(hud_frame, (5, self.height - 35), (self.width - 5, self.height - 5), (0, 0, 0), -1)
        u_val = pointer_data.get("u", 0.0)
        v_val = pointer_data.get("v", 0.0)
        cv2.putText(
            hud_frame,
            f"Camera: ({pointer_data.get('x', 0):.1f}, {pointer_data.get('y', 0):.1f}) -> Tableau: ({u_val:.1f}, {v_val:.1f})",
            (15, self.height - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            settings.COLOR_CYAN,
            1,
            cv2.LINE_AA,
        )

        return hud_frame


class SmartWhiteboardApplication:
    """Master application controller managing the primary event loop and all subsystems."""

    def __init__(self):
        print("==================================================")
        print(f"  {settings.APP_NAME}")
        print(f"  Version: {settings.APP_VERSION}")
        print("==================================================")

        # Subsystems initialization
        self.camera = CameraManager()
        self.has_camera = self.camera.open()

        self.skin_calibrator = SkinColorCalibrator(k_std=settings.CALIB_K_STD)
        self.stabilizer = PointerStabilizer(
            alpha=settings.SMOOTHING_ALPHA,
            deadzone=settings.DEADZONE_RADIUS,
            max_lost_frames=settings.MAX_LOST_FRAMES,
        )
        self.board_calibrator = BoardCalibrator()
        self.mapper = CoordinateMapper(calibrator=self.board_calibrator)
        self.remote = RemoteHandler()
        self.interface = WhiteboardInterface()
        self.interaction = InteractionManager(self.interface)
        self.dashboard = TechnicalDashboard()

        # Check for OpenCV Zoo MediaPipe ONNX models presence
        self.ml_detector: Optional[HandMLDetector] = None
        models_available = (
            os.path.exists(settings.HAND_ML_PALM_MODEL_PATH)
            and os.path.exists(settings.HAND_ML_HAND_MODEL_PATH)
        )

        if models_available:
            try:
                self.ml_detector = HandMLDetector()
                self.mode = "HAND_ML"
                print("[Detection] Modèles ONNX OpenCV Zoo détectés : mode HAND_ML activé par défaut.")
            except Exception as e:
                print(f"[Detection] Erreur initialisation HAND_ML: {e}. Repli sur MARKER.")
                self.mode = "MARKER"
        else:
            self.mode = "MARKER"
            print("[Detection] Modèles ONNX absents : repli automatique sur le mode MARKER.")
            print("            Pour activer HAND_ML, exécutez: python tools/download_models.py")

        # Operational state
        self.mouse_mode: bool = not self.has_camera
        self.show_dashboard: bool = settings.DASHBOARD_ENABLED_DEFAULT
        self.mouse_coords: List[int] = [settings.BOARD_WIDTH // 2, settings.BOARD_HEIGHT // 2]
        self.mouse_click_event: Optional[str] = None
        self.is_running: bool = False

        self._setup_windows()

    def _setup_windows(self) -> None:
        """Create and configure OpenCV windows."""
        # 1. Main Projected Surface Window
        cv2.namedWindow(settings.MAIN_WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(settings.MAIN_WINDOW_NAME, settings.BOARD_WIDTH, settings.BOARD_HEIGHT)

        # Mouse listener for the projected window
        def on_main_mouse(event, x, y, flags, param):
            self.mouse_coords[0] = x
            self.mouse_coords[1] = y
            if event == cv2.EVENT_LBUTTONDOWN:
                self.mouse_click_event = "LEFT_CLICK"
            elif event == cv2.EVENT_RBUTTONDOWN:
                self.mouse_click_event = "RIGHT_CLICK"

        cv2.setMouseCallback(settings.MAIN_WINDOW_NAME, on_main_mouse)

        # 2. Technical Supervisor Dashboard Window
        if self.show_dashboard:
            cv2.namedWindow(settings.DASHBOARD_WINDOW_NAME, cv2.WINDOW_AUTOSIZE)

    def run(self) -> None:
        """Main real-time application loop."""
        self.is_running = True
        print("\n[Application] Système démarré avec succès !")
        print("--- Raccourcis Clavier & Télécommande ---")
        print("  [Flèche Droite] / Clic Gauche : LEFT_CLICK (Sélection / Stylo Dessin)")
        print("  [Flèche Gauche] / Clic Droit  : RIGHT_CLICK (Retour Menu / Annuler)")
        print("  [m] : Commutation mode détection (HAND_ML -> MARKER -> SKIN)")
        print("  [s] / [Tab] : Basculer Contrôleur Souris simulée <-> Caméra")
        print("  [d] : Afficher / Masquer le Dashboard Technique")
        print("  [f] : Plein Écran")
        print("  [c] : Recalibrer la couleur de peau (mode SKIN)")
        print("  [q] ou [ESC] : Quitter l'application")
        print("-----------------------------------------\n")

        loop_times = []

        try:
            while self.is_running:
                loop_start = time.perf_counter()

                # 1. Process keyboard & presentation remote input
                key = cv2.waitKeyEx(15)
                if key in (ord("q"), ord("Q"), 27):
                    break

                # 'm' cycles: HAND_ML -> MARKER -> SKIN -> HAND_ML
                elif key in (ord("m"), ord("M")):
                    if self.mode == "HAND_ML":
                        self.mode = "MARKER"
                    elif self.mode == "MARKER":
                        self.mode = "SKIN"
                    elif self.mode == "SKIN":
                        # Try switching back to HAND_ML
                        models_available = (
                            os.path.exists(settings.HAND_ML_PALM_MODEL_PATH)
                            and os.path.exists(settings.HAND_ML_HAND_MODEL_PATH)
                        )
                        if models_available:
                            if self.ml_detector is None:
                                try:
                                    self.ml_detector = HandMLDetector()
                                except Exception as e:
                                    print(f"[Detection] Erreur: {e}")
                            if self.ml_detector is not None:
                                self.mode = "HAND_ML"
                            else:
                                self.mode = "MARKER"
                        else:
                            self.mode = "MARKER"
                            print("[Detection] Modèles ONNX introuvables dans assets/models/ ! Repli sur MARKER.")
                            print("            Exécutez 'python tools/download_models.py' pour télécharger les modèles.")

                    print(f"[Application] Mode de détection actif : {self.mode}")

                # 's' or Tab toggles mouse simulation mode
                elif key in (ord("s"), ord("S"), 9):
                    self.mouse_mode = not self.mouse_mode
                    print(f"[Application] Mode contrôleur : {'SOURIS SIMULEE' if self.mouse_mode else f'CAMERA ({self.mode})'}")

                # 'd' toggles Technical Supervisor Dashboard
                elif key in (ord("d"), ord("D")):
                    self.show_dashboard = not self.show_dashboard
                    if not self.show_dashboard:
                        cv2.destroyWindow(settings.DASHBOARD_WINDOW_NAME)
                    else:
                        cv2.namedWindow(settings.DASHBOARD_WINDOW_NAME, cv2.WINDOW_AUTOSIZE)

                # 'f' toggles Fullscreen
                elif key in (ord("f"), ord("F")):
                    val = cv2.getWindowProperty(settings.MAIN_WINDOW_NAME, cv2.WND_PROP_FULLSCREEN)
                    new_val = cv2.WINDOW_NORMAL if val == cv2.WINDOW_FULLSCREEN else cv2.WINDOW_FULLSCREEN
                    cv2.setWindowProperty(settings.MAIN_WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, new_val)

                # Process presentation remote click event
                remote_event = self.remote.process_key(key)
                if self.mouse_click_event is not None:
                    remote_event = self.mouse_click_event
                    self.mouse_click_event = None

                # 2. Frame acquisition and computer vision tracking
                camera_frame = None
                if not self.mouse_mode and self.has_camera:
                    ret, raw_frame = self.camera.read_frame()
                    if ret and raw_frame is not None:
                        camera_frame = raw_frame

                        # SKIN mode recalibration ROI
                        if key == ord("c") and self.mode == "SKIN":
                            roi_sz = settings.CALIB_ROI_SIZE
                            rx = (settings.FRAME_WIDTH - roi_sz) // 2
                            ry = (settings.FRAME_HEIGHT - roi_sz) // 2
                            roi = camera_frame[ry : ry + roi_sz, rx : rx + roi_sz]
                            self.skin_calibrator.calibrate_from_roi(roi)

                        # Detection branch based on active mode
                        if self.mode == "HAND_ML" and self.ml_detector is not None:
                            if self.board_calibrator.is_calibrated:
                                self.ml_detector.set_board_polygon(self.board_calibrator.src_corners)
                            raw_ptr = self.ml_detector.detect(camera_frame)
                        else:
                            raw_ptr, _ = detect_pointer(
                                camera_frame,
                                calibrator=self.skin_calibrator,
                                mode=self.mode,
                                stabilizer=self.stabilizer,
                            )

                        pointer = self.mapper.map_pointer(raw_ptr)
                    else:
                        pointer = {
                            "detected": False,
                            "x": 0.0,
                            "y": 0.0,
                            "raw_x": 0.0,
                            "raw_y": 0.0,
                            "area": 0,
                            "u": 0.0,
                            "v": 0.0,
                        }
                else:
                    # Mouse simulation mode
                    pointer = {
                        "detected": True,
                        "x": float(self.mouse_coords[0]),
                        "y": float(self.mouse_coords[1]),
                        "raw_x": float(self.mouse_coords[0]),
                        "raw_y": float(self.mouse_coords[1]),
                        "area": 1500,
                        "u": float(self.mouse_coords[0]),
                        "v": float(self.mouse_coords[1]),
                    }

                # 3. Process interaction logic (snapping, buttons, gestures, drawing)
                action = self.interaction.process_interaction(pointer, remote_event)
                if action:
                    print(f"[Interaction] Action: {action} ({self.interaction.last_action_message})")

                # 4. Measure Loop FPS
                dt = time.perf_counter() - loop_start
                loop_times.append(dt)
                if len(loop_times) > 15:
                    loop_times.pop(0)
                system_fps = 1.0 / np.mean(loop_times) if loop_times else 30.0
                camera_fps = self.camera.get_fps() if self.has_camera else 0.0

                # 5. Render Main Interface Window
                main_canvas = self.interface.render(pointer)
                cv2.imshow(settings.MAIN_WINDOW_NAME, main_canvas)

                # 6. Render Technical Supervisor Dashboard Window (if active)
                if self.show_dashboard:
                    hud_frame = self.dashboard.render(
                        camera_frame=camera_frame,
                        pointer_data=pointer,
                        calibrator=self.board_calibrator,
                        skin_calibrator=self.skin_calibrator,
                        stabilizer=self.stabilizer,
                        remote_handler=self.remote,
                        camera_fps=camera_fps,
                        system_fps=system_fps,
                        mode=self.mode,
                        mouse_mode=self.mouse_mode,
                    )
                    cv2.imshow(settings.DASHBOARD_WINDOW_NAME, hud_frame)

        except KeyboardInterrupt:
            print("\n[Application] Interruption utilisateur.")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Release all hardware and GUI resources cleanly."""
        print("[Application] Nettoyage et fermeture...")
        if self.has_camera:
            self.camera.release()
        cv2.destroyAllWindows()
        print("[Application] Arrêt complet terminé avec succès.")


def main():
    app = SmartWhiteboardApplication()
    app.run()


if __name__ == "__main__":
    main()
