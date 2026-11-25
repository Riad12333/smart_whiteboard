"""
OpenCV Zoo MediaPipe Wrappers Package for Smart Interactive Whiteboard.
Provides MPPalmDet (palm detector) and MPHandPose (21 3D landmarks regressor).
"""

from modules.ml.mp_palmdet import MPPalmDet
from modules.ml.mp_handpose import MPHandPose

__all__ = ["MPPalmDet", "MPHandPose"]
