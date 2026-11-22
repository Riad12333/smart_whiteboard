"""
Free functionalities module (Step 9).
Implements the 3 mandatory free features:
  1. Image display & interactive Zoom/Pan (Zoom in, Zoom out, 100% Reset)
  2. Coherent teaching sequence (Mini-lesson on Computer Vision with 3 pages & annotations)
  3. System usability, global reset & status dashboard
Part of the Smart Interactive Whiteboard project (USTHB 2026-2027).

NOTE: Image cropping, coordinate scaling, and zoom transforms are computed
using pure NumPy slicing and array interpolation.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from config import settings
from modules.drawing import DrawingEngine


# ==============================================================================
# 1. Image Display & Interactive Zoom / Pan
# ==============================================================================

class ImageZoomViewer:
    """
    Handles interactive loading, viewport rendering, and zooming (In/Out/Reset)
    for educational images on the whiteboard canvas.
    """

    def __init__(
        self,
        image_path: str = settings.DEFAULT_LESSON_IMAGE,
        viewport_w: int = 900,
        viewport_h: int = 540,
        viewport_x: int = 190,
        viewport_y: int = 90,
    ):
        self.image_path = image_path
        self.viewport_w = viewport_w
        self.viewport_h = viewport_h
        self.viewport_x = viewport_x
        self.viewport_y = viewport_y

        self.zoom_factor: float = 1.0
        self.min_zoom: float = settings.ZOOM_MIN
        self.max_zoom: float = settings.ZOOM_MAX
        self.zoom_step: float = settings.ZOOM_STEP

        # Load image from disk or generate fallback
        self.raw_image = self._load_image(self.image_path)
        self.img_h, self.img_w = self.raw_image.shape[:2]

        # Normalized pan center within raw image (0.5, 0.5 = center)
        self.pan_cx: float = 0.5
        self.pan_cy: float = 0.5

    def _load_image(self, path: str) -> np.ndarray:
        if os.path.exists(path):
            img = cv2.imread(path)
            if img is not None:
                return img
        # Fallback synthetic diagram
        img = np.full((600, 800, 3), 245, dtype=np.uint8)
        cv2.putText(img, "USTHB Computer Vision", (150, 280), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 200), 3)
        return img

    def zoom_in(self) -> float:
        """Increase zoom factor."""
        self.zoom_factor = min(self.max_zoom, round(self.zoom_factor + self.zoom_step, 2))
        return self.zoom_factor

    def zoom_out(self) -> float:
        """Decrease zoom factor."""
        self.zoom_factor = max(self.min_zoom, round(self.zoom_factor - self.zoom_step, 2))
        return self.zoom_factor

    def reset_view(self) -> None:
        """Restore initial 100% zoom and centered pan."""
        self.zoom_factor = 1.0
        self.pan_cx = 0.5
        self.pan_cy = 0.5

    def set_pan_from_pointer(self, u: float, v: float) -> None:
        """Focus zoom center on pointer position within viewport."""
        if (self.viewport_x <= u <= self.viewport_x + self.viewport_w) and (
            self.viewport_y <= v <= self.viewport_y + self.viewport_h
        ):
            rel_x = (u - self.viewport_x) / float(self.viewport_w)
            rel_y = (v - self.viewport_y) / float(self.viewport_h)
            self.pan_cx = float(np.clip(rel_x, 0.1, 0.9))
            self.pan_cy = float(np.clip(rel_y, 0.1, 0.9))

    def render(self, canvas: np.ndarray) -> None:
        """Crop and scale the active image ROI and paste into canvas viewport."""
        crop_w = int(self.img_w / self.zoom_factor)
        crop_h = int(self.img_h / self.zoom_factor)

        center_x = int(self.pan_cx * self.img_w)
        center_y = int(self.pan_cy * self.img_h)

        x1 = max(0, center_x - crop_w // 2)
        y1 = max(0, center_y - crop_h // 2)
        x2 = min(self.img_w, x1 + crop_w)
        y2 = min(self.img_h, y1 + crop_h)

        # Re-adjust start if reached boundary
        if x2 - x1 < crop_w and x1 > 0:
            x1 = max(0, x2 - crop_w)
        if y2 - y1 < crop_h and y1 > 0:
            y1 = max(0, y2 - crop_h)

        cropped = self.raw_image[y1:y2, x1:x2]
        if cropped.size == 0:
            return

        resized = cv2.resize(
            cropped,
            (self.viewport_w, self.viewport_h),
            interpolation=cv2.INTER_LINEAR,
        )

        # Paste onto canvas
        canvas[
            self.viewport_y : self.viewport_y + self.viewport_h,
            self.viewport_x : self.viewport_x + self.viewport_w,
        ] = resized

        # Viewport border
        cv2.rectangle(
            canvas,
            (self.viewport_x, self.viewport_y),
            (self.viewport_x + self.viewport_w, self.viewport_y + self.viewport_h),
            settings.COLOR_LIGHT_GRAY,
            2,
        )

        # Zoom level badge
        badge_text = f"Zoom: {int(self.zoom_factor * 100)}%"
        cv2.rectangle(canvas, (self.viewport_x + 10, self.viewport_y + 10), (self.viewport_x + 160, self.viewport_y + 45), (0, 0, 0), -1)
        cv2.putText(canvas, badge_text, (self.viewport_x + 20, self.viewport_y + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, settings.COLOR_YELLOW, 2)


# ==============================================================================
# 2. Coherent Teaching Lesson Sequence (USTHB Computer Vision)
# ==============================================================================

class LessonViewer:
    """
    Presents a coherent academic lesson structure:
      Page 1: Introduction (Color spaces, ITU-R BT.601, skin chrominance)
      Page 2: Mathematical Morphology (Erosion, Dilation, Opening, CCL)
      Page 3: Interactive Exercise & Annotation Workspace
    """

    def __init__(self, width: int = settings.BOARD_WIDTH, height: int = settings.BOARD_HEIGHT):
        self.width = width
        self.height = height
        self.current_page: int = 1
        self.total_pages: int = 3
        self.annotation_engine = DrawingEngine(width=width, height=height)
        self.is_annotation_active: bool = False

    def next_page(self) -> int:
        if self.current_page < self.total_pages:
            self.current_page += 1
        return self.current_page

    def prev_page(self) -> int:
        if self.current_page > 1:
            self.current_page -= 1
        return self.current_page

    def reset_lesson(self) -> None:
        self.current_page = 1
        self.annotation_engine.clear()
        self.is_annotation_active = False

    def toggle_annotation_mode(self) -> bool:
        self.is_annotation_active = not self.is_annotation_active
        if not self.is_annotation_active:
            self.annotation_engine.set_pen_state(False)
        return self.is_annotation_active

    def render(self, canvas: np.ndarray) -> None:
        """Render the lesson page contents and overlay drawing annotations."""
        # 1. Clean background panel
        cv2.rectangle(canvas, (60, 95), (self.width - 60, self.height - 95), (250, 250, 250), -1)
        cv2.rectangle(canvas, (60, 95), (self.width - 60, self.height - 95), settings.COLOR_LIGHT_GRAY, 2)

        font = cv2.FONT_HERSHEY_SIMPLEX

        # Page Header
        header = f"Lecon: Vision par Ordinateur (USTHB) - Page {self.current_page}/{self.total_pages}"
        cv2.putText(canvas, header, (85, 135), font, 0.8, (40, 40, 40), 2, cv2.LINE_AA)
        cv2.line(canvas, (85, 148), (self.width - 85, 148), (180, 180, 180), 1)

        if self.current_page == 1:
            # Page 1: Color spaces
            cv2.putText(canvas, "1. Espaces de Couleur & Segmentation de Peau", (85, 185), font, 0.72, (0, 120, 0), 2)
            cv2.putText(canvas, "- En BGR/RGB: la couleur est melangee a l'intensite lumineuse.", (95, 230), font, 0.6, (40, 40, 40), 1)
            cv2.putText(canvas, "- En YCrCb: Y isole la luminance, Cr et Cb isolent la chrominance pure.", (95, 270), font, 0.6, (40, 40, 40), 1)
            cv2.putText(canvas, "Formule ITU-R BT.601:", (95, 320), font, 0.65, (160, 50, 0), 2)
            cv2.putText(canvas, "  Y  =  0.2990 * R + 0.5870 * G + 0.1140 * B", (110, 360), font, 0.58, (20, 20, 20), 1)
            cv2.putText(canvas, "  Cr = (R - Y) * 0.7130 + 128", (110, 395), font, 0.58, (20, 20, 20), 1)
            cv2.putText(canvas, "  Cb = (B - Y) * 0.5640 + 128", (110, 430), font, 0.58, (20, 20, 20), 1)
            cv2.putText(canvas, "Seuils universels de secours: 133 <= Cr <= 173 et 77 <= Cb <= 127", (95, 480), font, 0.62, (0, 0, 180), 2)

        elif self.current_page == 2:
            # Page 2: Mathematical Morphology & CCL
            cv2.putText(canvas, "2. Morphologie Mathematique & Suivi de l'Index", (85, 185), font, 0.72, (0, 120, 0), 2)
            cv2.putText(canvas, "- Erosion (3x3): supprime les pixels de bruit isoles (bruit poivre et sel).", (95, 230), font, 0.6, (40, 40, 40), 1)
            cv2.putText(canvas, "- Dilatation (3x3): comble les trous et restaure la forme de la main.", (95, 270), font, 0.6, (40, 40, 40), 1)
            cv2.putText(canvas, "- Ouverture = Erosion suivie d'une Dilatation.", (95, 310), font, 0.6, (40, 40, 40), 1)
            cv2.putText(canvas, "- CCL (Composantes Connexes) isole la plus grande region (la main).", (95, 350), font, 0.6, (40, 40, 40), 1)
            cv2.putText(canvas, "- Bout du doigt (Fingertip) = pixel le plus eloigne du centroide (d^2 max).", (95, 390), font, 0.62, (160, 50, 0), 2)
            cv2.putText(canvas, "- Lissage temporel EMA: P_smooth = a * P_new + (1 - a) * P_prev", (95, 435), font, 0.62, (0, 0, 180), 2)

        elif self.current_page == 3:
            # Page 3: Exercise & Interactive Annotation
            cv2.putText(canvas, "3. Exercice Pratique: Schema du Pipeline & Annotation", (85, 185), font, 0.72, (0, 120, 0), 2)
            cv2.putText(canvas, "Consigne: Utilisez le stylo pour annoter les blocs ci-dessous:", (95, 225), font, 0.6, (40, 40, 40), 1)

            # Draw 3 exercise boxes
            cv2.rectangle(canvas, (120, 260), (380, 360), (225, 225, 225), -1)
            cv2.rectangle(canvas, (120, 260), (380, 360), (0, 0, 0), 2)
            cv2.putText(canvas, "Bloc A: Camera", (150, 315), font, 0.65, (0, 0, 0), 2)

            cv2.rectangle(canvas, (460, 260), (720, 360), (225, 225, 225), -1)
            cv2.rectangle(canvas, (460, 260), (720, 360), (0, 0, 0), 2)
            cv2.putText(canvas, "Bloc B: Detection", (485, 315), font, 0.65, (0, 0, 0), 2)

            cv2.rectangle(canvas, (800, 260), (1060, 360), (225, 225, 225), -1)
            cv2.rectangle(canvas, (800, 260), (1060, 360), (0, 0, 0), 2)
            cv2.putText(canvas, "Bloc C: Homographie DLT", (815, 315), font, 0.58, (0, 0, 0), 2)

            cv2.putText(canvas, "Exercice: Reliez les blocs et annotez les transformations avec votre index !", (95, 430), font, 0.62, (0, 100, 200), 2)

        # Blend user annotations on top of the lesson page
        annot_mask = np.any(self.annotation_engine.canvas != self.annotation_engine.bg_color, axis=-1)
        canvas[annot_mask] = self.annotation_engine.canvas[annot_mask]


# ==============================================================================
# 3. Global System Manager (Usability, Reset & Diagnostics)
# ==============================================================================

class SystemManager:
    """Manages global application reset, diagnostics, and component lifecycle."""

    def __init__(self, zoom_viewer: ImageZoomViewer, lesson_viewer: LessonViewer, drawing_engine: DrawingEngine):
        self.zoom_viewer = zoom_viewer
        self.lesson_viewer = lesson_viewer
        self.drawing_engine = drawing_engine

    def reset_all(self) -> None:
        """Global system reset: wipes drawings, resets lesson, and restores zoom to 100%."""
        self.drawing_engine.clear()
        self.zoom_viewer.reset_view()
        self.lesson_viewer.reset_lesson()
        print("[SystemManager] Global reset executed: all modules restored to initial state.")
