# OpenCV Zoo MediaPipe ONNX Models

This directory contains the lightweight pretrained ONNX neural network models from **OpenCV Zoo** used for the `HAND_ML` detection mode in the Smart Interactive Whiteboard project.

---

## 📦 Required Model Files

| Model Filename | Task | Input Resolution | Size (Bytes) | SHA-256 Checksum |
| :--- | :--- | :--- | :--- | :--- |
| `palm_detection_mediapipe_2023feb.onnx` | Palm detection (SSD + anchors) | $192 \times 192$ | 3,905,734 | `78ff51c38496b7fc8b8ebdb6cc8c1abb02fa6c38427c6848254cdaba57fcce7c` |
| `handpose_estimation_mediapipe_2023feb.onnx` | Hand skeleton regression (21 3D landmarks) | $224 \times 224$ | 4,099,621 | `db0898ae717b76b075d9bf563af315b29562e11f8df5027a1ef07b02bef6d81c` |

---

## 🚀 Automatic Download

Run the dedicated download tool from the project root:

```powershell
python tools/download_models.py
```

To verify the integrity of the downloaded files without re-downloading:
```powershell
python tools/download_models.py --verify
```

---

## 🌐 Manual Download (If Internet or Proxy is Blocked)

If the computer running the demonstration is offline or behind an institutional proxy/firewall, download both files manually using a web browser or curl/wget and place them in this folder (`assets/models/`):

1. **Palm Detection Model**:
   - Direct Download URL:  
     `https://huggingface.co/opencv/palm_detection_mediapipe/resolve/main/palm_detection_mediapipe_2023feb.onnx`
   - Repository Page:  
     `https://huggingface.co/opencv/palm_detection_mediapipe`
   - Target Local Path:  
     `assets/models/palm_detection_mediapipe_2023feb.onnx`

2. **Hand Pose Estimation Model**:
   - Direct Download URL:  
     `https://huggingface.co/opencv/handpose_estimation_mediapipe/resolve/main/handpose_estimation_mediapipe_2023feb.onnx`
   - Repository Page:  
     `https://huggingface.co/opencv/handpose_estimation_mediapipe`
   - Target Local Path:  
     `assets/models/handpose_estimation_mediapipe_2023feb.onnx`

---

## ⚖️ Origin & Licensing

- **Upstream Source**: Google MediaPipe (Apache 2.0 License).
- **ONNX Models & Wrappers**: OpenCV Model Zoo (`opencv/opencv_zoo`, Apache 2.0 License).
- **Execution Engine**: Native OpenCV DNN module (`cv2.dnn.readNet`), with zero external runtime dependencies (no `mediapipe` Python package required).
