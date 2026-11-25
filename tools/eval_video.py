"""
Video Evaluation Tool for Smart Interactive Whiteboard (Step 4quinquies - Partie D).
Evaluates pointer detection performance on video files:
  - Detection rate (% of frames with pointer detected)
  - Static hand jitter standard deviation (sigma_x, sigma_y, sigma)
  - Average inference / processing FPS and latency (ms)
  - Optional video annotation export with HUD telemetry
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from config import settings
from modules.detection import SkinColorCalibrator, PointerStabilizer, detect_pointer
from modules.detection_ml import HandMLDetector

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17)
]


def evaluate_video(
    video_path: str,
    mode: str = "HAND_ML",
    output_path: Optional[str] = None,
    max_frames: Optional[int] = None,
    static_window: Optional[Tuple[int, int]] = None,
) -> Dict:
    """
    Evaluate detection on a video file.
    Returns metrics dictionary with real measurements.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"\n=== Video Evaluation: {os.path.basename(video_path)} ===")
    print(f"Resolution: {width}x{height} | Native FPS: {video_fps:.1f} | Total Frames: {total_video_frames}")
    print(f"Evaluation Mode: {mode}\n")

    # Initialize detectors
    ml_detector = None
    stabilizer = PointerStabilizer(
        alpha=settings.SMOOTHING_ALPHA,
        deadzone=settings.DEADZONE_RADIUS,
        max_lost_frames=settings.MAX_LOST_FRAMES,
    )
    skin_calib = SkinColorCalibrator(k_std=settings.CALIB_K_STD)

    if mode == "HAND_ML":
        ml_detector = HandMLDetector()

    # Video writer setup
    writer = None
    if output_path:
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        writer = cv2.VideoWriter(output_path, fourcc, video_fps, (width, height))
        print(f"Exporting annotated video to: {output_path}")

    frames_processed = 0
    frames_detected = 0
    inference_times_ms = []
    positions_raw = []
    positions_smoothed = []

    t_start_total = time.perf_counter()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frames_processed += 1
        if max_frames and frames_processed > max_frames:
            break

        t_frame_start = time.perf_counter()

        if mode == "HAND_ML":
            res = ml_detector.detect(frame)
        else:
            res, _ = detect_pointer(frame, calibrator=skin_calib, mode=mode, stabilizer=stabilizer)

        dt_ms = (time.perf_counter() - t_frame_start) * 1000.0
        inference_times_ms.append(dt_ms)

        if res.get("detected", False):
            frames_detected += 1
            positions_raw.append((res.get("raw_x", 0.0), res.get("raw_y", 0.0)))
            positions_smoothed.append((res.get("x", 0.0), res.get("y", 0.0)))

        # Annotation overlay
        if writer is not None:
            annotated = frame.copy()
            if res.get("detected", False):
                landmarks = res.get("landmarks")
                if landmarks is not None and len(landmarks) == 21:
                    for p1, p2 in HAND_CONNECTIONS:
                        pt1 = (int(landmarks[p1, 0]), int(landmarks[p1, 1]))
                        pt2 = (int(landmarks[p2, 0]), int(landmarks[p2, 1]))
                        cv2.line(annotated, pt1, pt2, (255, 200, 100), 2, cv2.LINE_AA)
                    for i in range(21):
                        px, py = int(landmarks[i, 0]), int(landmarks[i, 1])
                        if i == 8:
                            cv2.circle(annotated, (px, py), 6, settings.COLOR_RED, -1)
                            cv2.circle(annotated, (px, py), 12, settings.COLOR_YELLOW, 2)
                        else:
                            cv2.circle(annotated, (px, py), 3, (255, 255, 255), -1)
                else:
                    sx, sy = int(res.get("x", 0)), int(res.get("y", 0))
                    cv2.circle(annotated, (sx, sy), 8, settings.COLOR_RED, -1)
                    cv2.drawMarker(annotated, (sx, sy), settings.COLOR_GREEN, cv2.MARKER_CROSS, 20, 2)

            # HUD Telemetry
            cv2.rectangle(annotated, (5, 5), (width - 5, 45), (0, 0, 0), -1)
            det_label = "DETECTE" if res.get("detected") else "PERDU"
            cv2.putText(
                annotated,
                f"Mode: {mode} | Frame: {frames_processed}/{total_video_frames} | {det_label} | Latency: {dt_ms:.1f}ms",
                (15, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                settings.COLOR_GREEN if res.get("detected") else settings.COLOR_RED,
                1,
                cv2.LINE_AA,
            )
            writer.write(annotated)

    cap.release()
    if writer is not None:
        writer.release()

    t_total = time.perf_counter() - t_start_total

    # Metrics calculation
    det_rate = (frames_detected / frames_processed * 100.0) if frames_processed > 0 else 0.0
    avg_inf_ms = float(np.mean(inference_times_ms)) if inference_times_ms else 0.0
    effective_fps = frames_processed / t_total if t_total > 0 else 0.0

    # Jitter standard deviation calculation
    # If static window is specified (start_idx, end_idx), compute on that segment;
    # otherwise compute on the most stable 30 consecutive detected frames.
    sigma_raw = 0.0
    sigma_smoothed = 0.0

    if len(positions_raw) >= 10:
        if static_window:
            s_idx, e_idx = static_window
            pts_raw = positions_raw[s_idx:e_idx]
            pts_sm = positions_smoothed[s_idx:e_idx]
        else:
            # Find the most static 30-frame window (minimal standard deviation)
            win_size = min(30, len(positions_raw))
            best_std = float("inf")
            best_window_raw = positions_raw[:win_size]
            best_window_sm = positions_smoothed[:win_size]

            for i in range(len(positions_raw) - win_size + 1):
                subset = positions_raw[i : i + win_size]
                xs = [p[0] for p in subset]
                ys = [p[1] for p in subset]
                current_std = math.hypot(np.std(xs), np.std(ys))
                if current_std < best_std:
                    best_std = current_std
                    best_window_raw = subset
                    best_window_sm = positions_smoothed[i : i + win_size]

            pts_raw = best_window_raw
            pts_sm = best_window_sm

        xs_raw = [p[0] for p in pts_raw]
        ys_raw = [p[1] for p in pts_raw]
        sigma_raw = float(math.hypot(np.std(xs_raw), np.std(ys_raw)))

        xs_sm = [p[0] for p in pts_sm]
        ys_sm = [p[1] for p in pts_sm]
        sigma_smoothed = float(math.hypot(np.std(xs_sm), np.std(ys_sm)))

    metrics = {
        "video_path": video_path,
        "mode": mode,
        "total_frames": frames_processed,
        "detected_frames": frames_detected,
        "detection_rate_pct": round(det_rate, 2),
        "mean_latency_ms": round(avg_inf_ms, 2),
        "effective_fps": round(effective_fps, 1),
        "jitter_raw_std_px": round(sigma_raw, 2),
        "jitter_smoothed_std_px": round(sigma_smoothed, 2),
        "jitter_reduction_pct": round((1.0 - (sigma_smoothed / (sigma_raw + 1e-6))) * 100.0, 1) if sigma_raw > 0 else 0.0
    }

    # Print summary table
    print("=" * 60)
    print("  EVALUATION SUMMARY")
    print("=" * 60)
    print(f"  Mode                 : {metrics['mode']}")
    print(f"  Frames Processed     : {metrics['total_frames']}")
    print(f"  Frames Detected      : {metrics['detected_frames']}")
    print(f"  Detection Rate       : {metrics['detection_rate_pct']}%")
    print(f"  Mean Latency         : {metrics['mean_latency_ms']} ms")
    print(f"  Effective Speed      : {metrics['effective_fps']} FPS")
    print(f"  Raw Jitter (Std)     : {metrics['jitter_raw_std_px']} px")
    print(f"  Smoothed Jitter (Std): {metrics['jitter_smoothed_std_px']} px")
    print(f"  Jitter Attenuation   : {metrics['jitter_reduction_pct']}%")
    print("=" * 60 + "\n")

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate pointer detection on video.")
    parser.add_argument("video", type=str, help="Path to input video file.")
    parser.add_argument("--mode", type=str, choices=["HAND_ML", "MARKER", "SKIN"], default="HAND_ML", help="Detection mode.")
    parser.add_argument("--output", type=str, default=None, help="Path to export annotated video.")
    parser.add_argument("--max-frames", type=int, default=None, help="Maximum number of frames to process.")
    args = parser.parse_args()

    evaluate_video(args.video, mode=args.mode, output_path=args.output, max_frames=args.max_frames)
