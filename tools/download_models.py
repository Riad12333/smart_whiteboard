"""
Model Downloader for Smart Interactive Whiteboard (Step 4quinquies).
Downloads the official MediaPipe Palm Detection and HandPose Estimation ONNX models
from the OpenCV Zoo Hugging Face repositories into assets/models/.

Calculates and displays real byte size and SHA-256 checksums.
"""

import argparse
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "assets" / "models"

# Official OpenCV Zoo Model Metadata on Hugging Face
MODELS_INFO = {
    "palm_detection_mediapipe_2023feb.onnx": {
        "url": "https://huggingface.co/opencv/palm_detection_mediapipe/resolve/main/palm_detection_mediapipe_2023feb.onnx",
        "expected_bytes": 3905734,
        "expected_sha256": "78ff51c38496b7fc8b8ebdb6cc8c1abb02fa6c38427c6848254cdaba57fcce7c",
        "description": "MediaPipe Palm Detection (SSD anchor-based detector, 192x192 input)"
    },
    "handpose_estimation_mediapipe_2023feb.onnx": {
        "url": "https://huggingface.co/opencv/handpose_estimation_mediapipe/resolve/main/handpose_estimation_mediapipe_2023feb.onnx",
        "expected_bytes": 4099621,
        "expected_sha256": "db0898ae717b76b075d9bf563af315b29562e11f8df5027a1ef07b02bef6d81c",
        "description": "MediaPipe Hand Pose Estimation (21 3D landmarks regressor, 224x224 input)"
    }
}


def compute_file_sha256(filepath: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def download_with_progress(url: str, dest_path: Path):
    """Download a file with console progress indicator."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SmartWhiteboard-ModelDownloader/1.0"}
    )
    with urllib.request.urlopen(req) as response:
        total_size = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 65536

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        temp_dest = dest_path.with_suffix(".tmp")

        with open(temp_dest, "wb") as out_file:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    mb_down = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    sys.stdout.write(f"\r  Downloading: {mb_down:.2f} MB / {mb_total:.2f} MB ({percent:.1f}%)")
                    sys.stdout.flush()
                else:
                    sys.stdout.write(f"\r  Downloading: {downloaded / (1024 * 1024):.2f} MB")
                    sys.stdout.flush()

        print()  # New line after progress
        if dest_path.exists():
            dest_path.unlink()
        temp_dest.rename(dest_path)


def download_models(force: bool = False, verify_only: bool = False) -> bool:
    """
    Download and verify both ONNX models.
    Returns True if all models are present and valid, False otherwise.
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    all_valid = True

    print(f"=== OpenCV Zoo MediaPipe ONNX Models Downloader ===")
    print(f"Target directory: {MODELS_DIR}\n")

    for filename, info in MODELS_INFO.items():
        dest = MODELS_DIR / filename
        print(f"[*] Model: {filename}")
        print(f"    Description: {info['description']}")
        print(f"    Source URL:  {info['url']}")

        already_exists = dest.exists()
        if already_exists and not force:
            print(f"    File already exists locally.")
        elif verify_only:
            print(f"    [FAIL] File missing in verify-only mode.")
            all_valid = False
            continue
        else:
            print(f"    Starting download...")
            try:
                download_with_progress(info["url"], dest)
            except Exception as e:
                print(f"    [ERROR] Download failed: {e}")
                all_valid = False
                continue

        # Measure actual file size and hash
        actual_bytes = dest.stat().st_size
        actual_sha256 = compute_file_sha256(dest)

        print(f"    Size:   {actual_bytes:,} bytes (expected: {info['expected_bytes']:,})")
        print(f"    SHA256: {actual_sha256}")

        if actual_bytes == info["expected_bytes"] and actual_sha256 == info["expected_sha256"]:
            print(f"    Status: [VERIFIED OK]")
        else:
            print(f"    Status: [WARNING - HASH OR SIZE MISMATCH]")
            all_valid = False
        print()

    if all_valid:
        print("[SUCCESS] All OpenCV Zoo MediaPipe models are downloaded and integrity verified.")
    else:
        print("[WARNING] One or more models failed verification. Check network connection or proxy.")
    return all_valid


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download OpenCV Zoo MediaPipe ONNX models.")
    parser.add_argument("--force", action="store_true", help="Force re-download even if files exist.")
    parser.add_argument("--verify", action="store_true", help="Only verify existing files without downloading.")
    args = parser.parse_args()

    success = download_models(force=args.force, verify_only=args.verify)
    sys.exit(0 if success else 1)
