"""
Interaction manager module (Steps 7, 8, 9 & 10).
Integrates:
  - Excalidraw UI navigation
  - Drawing interactions (colors, eraser, thicknesses, undo, pen toggle)
  - Image Zoom interactions (Zoom in, Zoom out, Reset)
  - Lesson sequence interactions (Next page, Prev page, Annotate)
  - Global Reset & Recalibration
Part of the Smart Interactive Whiteboard project (USTHB 2026-2027).
"""

import sys
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from config import settings
from modules.interface import Button, WhiteboardInterface


class InteractionManager:
    """Coordinates pointer tracking, remote control click events, and interface navigation."""

    def __init__(self, interface: WhiteboardInterface):
        self.interface = interface
        self.last_action_message: str = "Prêt"

    def process_interaction(
        self, pointer: Dict[str, Union[bool, float, int]], remote_event: Optional[str]
    ) -> Optional[str]:
        """
        Process current frame tracking coordinates and remote HID button events.
        """
        u = float(pointer.get("u", 0.0))
        v = float(pointer.get("v", 0.0))
        detected = bool(pointer.get("detected", False))

        # Check button hover and magnetic snap
        hovered_btn = self.interface.update_hover(u, v) if detected else None

        # 1. If inside DRAWING_VIEW
        if self.interface.current_view == "DRAWING_VIEW":
            if remote_event == "LEFT_CLICK":
                self.interface.trigger_click_ripple(u, v)
                if hovered_btn is not None:
                    return self._handle_button_action(hovered_btn.button_id)
                else:
                    # Clicking on canvas toggles Pen Down <-> Pen Up
                    state = self.interface.drawing_engine.toggle_pen()
                    self.last_action_message = f"Stylo: {'POSE' if state else 'LEVE'}"
                    return "TOGGLE_PEN"

            elif remote_event == "RIGHT_CLICK":
                self.interface.trigger_click_ripple(u, v)
                if self.interface.drawing_engine.is_pen_down:
                    # Next pour lever / Previous pour annuler
                    self.interface.drawing_engine.set_pen_state(False)
                    self.last_action_message = "Stylo levé"
                    return "TOGGLE_PEN"
                else:
                    # If pen already up, right-click triggers Undo
                    self.interface.drawing_engine.undo()
                    self.last_action_message = "Trait annulé (Undo)"
                    return "UNDO"

            # If pen is down, add point to continuous stroke
            if detected and self.interface.drawing_engine.is_pen_down:
                self.interface.drawing_engine.add_point(u, v)

            return None

        # 2. If inside LESSON_VIEW with active annotation mode
        if self.interface.current_view == "LESSON_VIEW":
            if self.interface.lesson_viewer.is_annotation_active:
                if remote_event == "LEFT_CLICK" and hovered_btn is None and (v < self.interface.height - 90):
                    self.interface.trigger_click_ripple(u, v)
                    self.interface.lesson_viewer.annotation_engine.toggle_pen()
                    return "TOGGLE_LESSON_PEN"
                if detected and self.interface.lesson_viewer.annotation_engine.is_pen_down and (v < self.interface.height - 90):
                    self.interface.lesson_viewer.annotation_engine.add_point(u, v)

        # 3. Universal RIGHT_CLICK: Back to Main Menu from any submenu
        if remote_event == "RIGHT_CLICK":
            self.interface.trigger_click_ripple(u, v)
            if self.interface.current_view != "MAIN":
                self.interface.set_view("MAIN")
                self.last_action_message = "Retour au Menu Principal"
                return "BACK_TO_MAIN"
            return None

        # 4. LEFT_CLICK on hovered button
        if remote_event == "LEFT_CLICK" and hovered_btn is not None:
            self.interface.trigger_click_ripple(u, v)
            hovered_btn.is_active = True
            return self._handle_button_action(hovered_btn.button_id)

        return None

    def _handle_button_action(self, btn_id: str) -> str:
        """Route button identifier to corresponding application subsystem action."""
        # Main Navigation
        if btn_id in ("nav_home", "btn_back"):
            self.interface.set_view("MAIN")
            self.last_action_message = "Menu Principal"
            return "BACK_TO_MAIN"

        elif btn_id in ("nav_pen", "card_draw", "nav_draw"):
            self.interface.set_view("DRAWING_VIEW")
            self.interface.drawing_engine.is_eraser = False
            self.last_action_message = "Espace Dessin Libre"
            return "OPEN_DRAWING"

        elif btn_id in ("nav_image", "card_image"):
            self.interface.set_view("IMAGE_VIEW")
            self.last_action_message = "Visualiseur d'Image"
            return "OPEN_IMAGE"

        elif btn_id in ("nav_lesson", "card_lesson"):
            self.interface.set_view("LESSON_VIEW")
            self.last_action_message = "Mini-Leçon USTHB"
            return "OPEN_LESSON"

        elif btn_id in ("nav_settings", "card_settings"):
            self.interface.set_view("SETTINGS_VIEW")
            self.last_action_message = "Paramètres"
            return "OPEN_SETTINGS"

        # Drawing Tool Actions
        elif btn_id in ("nav_eraser", "draw_eraser"):
            self.interface.drawing_engine.toggle_eraser()
            self.last_action_message = "Outil Gomme activé"
            return "ERASER"

        elif btn_id in ("btn_undo", "draw_undo"):
            self.interface.drawing_engine.undo()
            self.last_action_message = "Trait annulé (Undo)"
            return "UNDO"

        elif btn_id == "draw_clear":
            self.interface.drawing_engine.clear()
            self.last_action_message = "Tableau effacé"
            return "CLEAR"

        # Safe 4 Excalidraw Colors
        elif btn_id == "color_black":
            self.interface.drawing_engine.set_color(settings.COLOR_DRAW_BLACK)
            self.last_action_message = "Couleur: Noir"
            return "COLOR_BLACK"

        elif btn_id in ("color_blue", "draw_pen_blue"):
            self.interface.drawing_engine.set_color(settings.COLOR_DRAW_BLUE)
            self.last_action_message = "Couleur: Bleu"
            return "COLOR_BLUE"

        elif btn_id in ("color_red", "draw_pen_red"):
            self.interface.drawing_engine.set_color(settings.COLOR_DRAW_RED)
            self.last_action_message = "Couleur: Rouge"
            return "COLOR_RED"

        elif btn_id == "color_purple":
            self.interface.drawing_engine.set_color(settings.COLOR_DRAW_PURPLE)
            self.last_action_message = "Couleur: Violet"
            return "COLOR_PURPLE"

        # 3 Thicknesses
        elif btn_id == "thick_thin":
            self.interface.drawing_engine.set_thickness(settings.PEN_THIN_THICKNESS)
            self.last_action_message = "Épaisseur: Fine"
            return "THICK_THIN"

        elif btn_id == "thick_med":
            self.interface.drawing_engine.set_thickness(settings.PEN_MEDIUM_THICKNESS)
            self.last_action_message = "Épaisseur: Moyenne"
            return "THICK_MED"

        elif btn_id == "thick_thick":
            self.interface.drawing_engine.set_thickness(settings.PEN_THICK_THICKNESS)
            self.last_action_message = "Épaisseur: Épaisse"
            return "THICK_THICK"

        # Lesson Navigation
        elif btn_id in ("lesson_next", "btn_lesson_next"):
            p = self.interface.lesson_viewer.next_page()
            self.last_action_message = f"Leçon: Page {p}"
            return "LESSON_NEXT"

        elif btn_id in ("lesson_prev", "btn_lesson_prev"):
            p = self.interface.lesson_viewer.prev_page()
            self.last_action_message = f"Leçon: Page {p}"
            return "LESSON_PREV"

        elif btn_id in ("lesson_annot", "btn_lesson_annot"):
            active = self.interface.lesson_viewer.toggle_annotation_mode()
            self.last_action_message = f"Annotation: {'ACTIVEE' if active else 'DESACTIVEE'}"
            return "LESSON_ANNOT_TOGGLE"

        elif btn_id in ("lesson_clear", "btn_lesson_clear"):
            self.interface.lesson_viewer.annotation_engine.clear()
            self.last_action_message = "Notes effacées"
            return "LESSON_CLEAR"

        # Image Zoom Actions
        elif btn_id in ("img_zoom_in", "btn_zoom_in"):
            z = self.interface.zoom_viewer.zoom_in()
            self.last_action_message = f"Zoom: {int(z * 100)}%"
            return "ZOOM_IN"

        elif btn_id in ("img_zoom_out", "btn_zoom_out"):
            z = self.interface.zoom_viewer.zoom_out()
            self.last_action_message = f"Zoom: {int(z * 100)}%"
            return "ZOOM_OUT"

        elif btn_id in ("img_reset", "btn_zoom_reset"):
            self.interface.zoom_viewer.reset_view()
            self.last_action_message = "Zoom réinitialisé (100%)"
            return "ZOOM_RESET"

        # Settings Actions
        elif btn_id in ("btn_reset", "set_reset"):
            self.interface.system_manager.reset_all()
            self.interface.set_view("MAIN")
            self.last_action_message = "Réinitialisation Globale (Reset)"
            return "GLOBAL_RESET"

        elif btn_id == "btn_recalib":
            self.last_action_message = "Lancement de la Recalibration"
            return "RECALIBRATE"

        return btn_id
