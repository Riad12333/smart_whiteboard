"""
Excalidraw-inspired Graphical User Interface (GUI) module (Steps 7, 8, 9 & 10).
Features:
  - White canvas with subtle dot grid
  - Floating top toolbar pill with soft shadow (Accueil, Stylo, Gomme, Formes, Images, Leçons, Réglages)
  - Top-right status pill ("• Suivi actif")
  - Home screen with 4 large hand-drawn cards (Dessiner, Images, Leçons, Réglages)
  - Left floating vertical palette in drawing mode (4 safe colors, 3 thicknesses, Undo)
  - Magnetic cursor snapping (SNAP_RADIUS = 75px)
  - Patrick Hand handwritten font rendering
  - Toast message pill at bottom ("Stylo posé · Next pour lever · Previous pour annuler")
  - Ripple wave click feedback (150ms animation)
Part of the Smart Interactive Whiteboard project (USTHB 2026-2027).
"""

import math
import os
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np
import pygame

from config import settings
from modules.drawing import DrawingEngine
from modules.features import ImageZoomViewer, LessonViewer, SystemManager


class Button:
    """
    Interactive button element supporting rectangular hit-testing,
    magnetic snapping, and smooth hover/active transitions.
    """

    def __init__(
        self,
        button_id: str,
        label: str,
        x: int = 0,
        y: int = 0,
        width: int = 100,
        height: int = 50,
        icon_name: str = "",
        accent_color: Tuple[int, int, int] = settings.EXCALI_PURPLE,
        rect: Optional[pygame.Rect] = None,
    ):
        self.button_id = button_id
        self.element_id = button_id  # Compatibility alias
        self.label = label

        if rect is not None:
            self.rect = rect
        else:
            self.rect = pygame.Rect(x, y, width, height)

        self.base_rect = self.rect.copy()
        self.icon_name = icon_name
        self.accent_color = accent_color

        self.is_hovered: bool = False
        self.is_active: bool = False
        self.is_selected: bool = False

    def contains(self, u: float, v: float) -> bool:
        """Inclusive point-in-rectangle collision test."""
        iu, iv = int(round(u)), int(round(v))
        return (self.rect.left <= iu <= self.rect.right) and (self.rect.top <= iv <= self.rect.bottom)

    def distance_to(self, u: float, v: float) -> float:
        """Euclidean distance from point (u, v) to the button center."""
        cx, cy = self.rect.center
        return math.hypot(u - cx, v - cy)


# Compatibility alias
InteractiveElement = Button


class ExcalidrawInterface:
    """Complete Excalidraw-styled Whiteboard UI engine powered by Pygame and NumPy."""

    def __init__(
        self,
        width: int = settings.BOARD_WIDTH,
        height: int = settings.BOARD_HEIGHT,
    ):
        self.width = width
        self.height = height

        # Initialize Pygame subsystems if not already active
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()

        # Load Patrick Hand handwritten font
        font_path = settings.FONT_HANDWRITTEN
        if os.path.exists(font_path):
            self.font_title = pygame.font.Font(font_path, 52)
            self.font_subtitle = pygame.font.Font(font_path, 25)
            self.font_card = pygame.font.Font(font_path, 32)
            self.font_card_sub = pygame.font.Font(font_path, 20)
            self.font_nav = pygame.font.Font(font_path, 19)
            self.font_toast = pygame.font.Font(font_path, 22)
            self.font_badge = pygame.font.Font(font_path, 18)
        else:
            self.font_title = pygame.font.SysFont("segoeprint", 44)
            self.font_subtitle = pygame.font.SysFont("segoeprint", 22)
            self.font_card = pygame.font.SysFont("segoeprint", 26)
            self.font_card_sub = pygame.font.SysFont("segoeprint", 16)
            self.font_nav = pygame.font.SysFont("segoeprint", 15)
            self.font_toast = pygame.font.SysFont("segoeprint", 18)
            self.font_badge = pygame.font.SysFont("segoeprint", 15)

        # Main rendering surface
        self.screen_surface = pygame.Surface((self.width, self.height))

        # Core application subsystems
        self.drawing_engine = DrawingEngine(width=width, height=height)
        self.zoom_viewer = ImageZoomViewer()
        self.lesson_viewer = LessonViewer(width=width, height=height)
        self.system_manager = SystemManager(self.zoom_viewer, self.lesson_viewer, self.drawing_engine)

        # State management
        self.current_view: str = "MAIN"  # "MAIN", "DRAWING_VIEW", "LESSON_VIEW", "IMAGE_VIEW", "SETTINGS_VIEW"
        self.toast_message: str = "Bienvenue sur le Tableau Blanc Interactif (USTHB)"
        self.toast_timer: float = time.time() + 4.0

        # Click ripple wave animation state: (x, y, start_time)
        self.active_ripples: List[Tuple[float, float, float]] = []

        # Snapped pointer coordinates
        self.snapped_u: float = float(width // 2)
        self.snapped_v: float = float(height // 2)
        self.is_snapped: bool = False

        self._build_ui_layout()

    def _build_ui_layout(self) -> None:
        """Create navigation toolbar, home cards, side palettes, and subview buttons."""
        # 1. Top floating navigation pill (Centered at top)
        pill_w = 690
        pill_h = 76
        pill_x = (self.width - pill_w) // 2
        pill_y = 18
        self.top_pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)

        nav_items = [
            ("nav_home", "Accueil", "home"),
            ("nav_pen", "Stylo", "pen"),
            ("nav_eraser", "Gomme", "eraser"),
            ("nav_shapes", "Formes", "shapes"),
            ("nav_image", "Images", "image"),
            ("nav_lesson", "Leçons", "lesson"),
            ("nav_settings", "Réglages", "settings"),
        ]

        self.nav_buttons: List[Button] = []
        btn_w = (pill_w - 20) // len(nav_items)
        for i, (elem_id, label, icon) in enumerate(nav_items):
            bx = pill_x + 10 + i * btn_w
            by = pill_y + 8
            rect = pygame.Rect(bx, by, btn_w, pill_h - 16)
            self.nav_buttons.append(Button(elem_id, label, rect=rect, icon_name=icon))

        # Default select "Accueil"
        self.nav_buttons[0].is_selected = True

        # 2. Home screen 4 main action cards (Mockup 2)
        card_w = 240
        card_h = 220
        card_y = 290
        spacing = 30
        total_w = 4 * card_w + 3 * spacing
        start_x = (self.width - total_w) // 2

        self.home_cards: List[Button] = [
            Button("card_draw", "Dessiner", rect=pygame.Rect(start_x, card_y, card_w, card_h), icon_name="pen", accent_color=settings.EXCALI_BLUE),
            Button("card_image", "Images", rect=pygame.Rect(start_x + (card_w + spacing), card_y, card_w, card_h), icon_name="image", accent_color=settings.COLOR_DRAW_RED),
            Button("card_lesson", "Leçons", rect=pygame.Rect(start_x + 2 * (card_w + spacing), card_y, card_w, card_h), icon_name="lesson", accent_color=settings.COLOR_DRAW_PURPLE),
            Button("card_settings", "Réglages", rect=pygame.Rect(start_x + 3 * (card_w + spacing), card_y, card_w, card_h), icon_name="settings", accent_color=settings.COLOR_DRAW_BLACK),
        ]

        # 3. Left vertical floating palette for Drawing mode (Mockup 1)
        pal_w = 72
        pal_h = 490
        pal_x = 24
        pal_y = 115
        self.left_palette_rect = pygame.Rect(pal_x, pal_y, pal_w, pal_h)

        self.palette_colors = [
            ("color_black", settings.COLOR_DRAW_BLACK),
            ("color_blue", settings.COLOR_DRAW_BLUE),
            ("color_red", settings.COLOR_DRAW_RED),
            ("color_purple", settings.COLOR_DRAW_PURPLE),
        ]

        self.palette_thicknesses = [
            ("thick_thin", settings.PEN_THIN_THICKNESS),
            ("thick_med", settings.PEN_MEDIUM_THICKNESS),
            ("thick_thick", settings.PEN_THICK_THICKNESS),
        ]

        self.drawing_palette_buttons: List[Button] = []
        cx = self.left_palette_rect.centerx
        cy = self.left_palette_rect.top + 36

        # 4 Color buttons
        for col_id, col_val in self.palette_colors:
            rect = pygame.Rect(cx - 22, cy - 22, 44, 44)
            self.drawing_palette_buttons.append(Button(col_id, "", rect=rect, icon_name="color"))
            cy += 48

        cy += 24
        # 3 Thickness buttons
        for th_id, th_val in self.palette_thicknesses:
            rect = pygame.Rect(cx - 24, cy - 14, 48, 28)
            self.drawing_palette_buttons.append(Button(th_id, "", rect=rect, icon_name="thickness"))
            cy += 38

        cy += 28
        # Undo button
        rect = pygame.Rect(cx - 22, cy - 22, 44, 44)
        self.drawing_palette_buttons.append(Button("btn_undo", "Undo", rect=rect, icon_name="undo"))

        # 4. Subview buttons
        # Image viewer controls
        self.image_buttons: List[Button] = [
            Button("img_zoom_in", "Zoom +", rect=pygame.Rect(self.width // 2 - 160, self.height - 70, 90, 42)),
            Button("img_zoom_out", "Zoom -", rect=pygame.Rect(self.width // 2 - 50, self.height - 70, 90, 42)),
            Button("img_reset", "100%", rect=pygame.Rect(self.width // 2 + 60, self.height - 70, 90, 42)),
        ]

        # Lesson viewer controls
        self.lesson_buttons: List[Button] = [
            Button("lesson_prev", "< Précédent", rect=pygame.Rect(self.width // 2 - 270, self.height - 70, 125, 42)),
            Button("lesson_next", "Suivant >", rect=pygame.Rect(self.width // 2 - 125, self.height - 70, 125, 42)),
            Button("lesson_annot", "Annoter", rect=pygame.Rect(self.width // 2 + 20, self.height - 70, 110, 42)),
            Button("lesson_clear", "Effacer Notes", rect=pygame.Rect(self.width // 2 + 150, self.height - 70, 130, 42)),
        ]

        # Settings controls
        self.settings_buttons: List[Button] = [
            Button("btn_reset", "Réinitialisation Globale", rect=pygame.Rect(self.width // 2 - 250, 280, 500, 120)),
            Button("btn_recalib", "Recalibrer Caméra", rect=pygame.Rect(self.width // 2 - 250, 430, 500, 60)),
        ]

    def get_active_buttons(self) -> List[Button]:
        """Return all interactive buttons currently active in the visible view."""
        buttons = list(self.nav_buttons)
        if self.current_view == "MAIN":
            buttons.extend(self.home_cards)
        elif self.current_view == "DRAWING_VIEW":
            buttons.extend(self.drawing_palette_buttons)
        elif self.current_view == "IMAGE_VIEW":
            buttons.extend(self.image_buttons)
        elif self.current_view == "LESSON_VIEW":
            buttons.extend(self.lesson_buttons)
        elif self.current_view == "SETTINGS_VIEW":
            buttons.extend(self.settings_buttons)
        return buttons

    def set_view(self, view_name: str) -> None:
        """Switch views and update toolbar active state."""
        self.current_view = view_name
        self.drawing_engine.set_pen_state(False)

        # Update nav buttons active highlight
        for btn in self.nav_buttons:
            if view_name == "MAIN" and btn.button_id == "nav_home":
                btn.is_selected = True
            elif view_name == "DRAWING_VIEW" and btn.button_id == "nav_pen":
                btn.is_selected = True
            elif view_name == "IMAGE_VIEW" and btn.button_id == "nav_image":
                btn.is_selected = True
            elif view_name == "LESSON_VIEW" and btn.button_id == "nav_lesson":
                btn.is_selected = True
            elif view_name == "SETTINGS_VIEW" and btn.button_id == "nav_settings":
                btn.is_selected = True
            else:
                btn.is_selected = False

    def update_hover(self, u: float, v: float) -> Optional[Button]:
        """
        Identify which button is hovered or magnetically targeted by pointer (u, v).
        """
        buttons = self.get_active_buttons()
        hovered_button: Optional[Button] = None
        min_dist = float("inf")

        # 1. Direct hit-testing
        for btn in buttons:
            btn.is_hovered = False
            if btn.contains(u, v):
                hovered_button = btn
                btn.is_hovered = True

        # 2. Magnetic snap if not directly inside any button
        if hovered_button is None:
            for btn in buttons:
                dist = btn.distance_to(u, v)
                if dist < min_dist and dist <= settings.SNAP_RADIUS:
                    min_dist = dist
                    hovered_button = btn

            if hovered_button is not None:
                hovered_button.is_hovered = True

        return hovered_button

    def update_magnetic_snap(self, raw_u: float, raw_v: float, detected: bool) -> Tuple[float, float, Optional[str]]:
        """
        Calculate smooth magnetic snapped cursor coordinates.
        """
        if not detected:
            self.is_snapped = False
            self.snapped_u, self.snapped_v = raw_u, raw_v
            return raw_u, raw_v, None

        hovered = self.update_hover(raw_u, raw_v)
        if hovered is not None:
            cx, cy = hovered.rect.center
            snap_factor = 0.65
            self.snapped_u = raw_u + snap_factor * (cx - raw_u)
            self.snapped_v = raw_v + snap_factor * (cy - raw_v)
            self.is_snapped = True
            return self.snapped_u, self.snapped_v, hovered.button_id

        self.is_snapped = False
        self.snapped_u, self.snapped_v = raw_u, raw_v
        return raw_u, raw_v, None

    def show_toast(self, message: str, duration_sec: float = 3.0) -> None:
        """Display an Excalidraw floating toast at the bottom."""
        self.toast_message = message
        self.toast_timer = time.time() + duration_sec

    def trigger_click_ripple(self, u: float, v: float) -> None:
        """Trigger an expanding circular ripple wave upon clicking."""
        self.active_ripples.append((u, v, time.time()))

    # ==========================================================================
    # Rendering Pipeline
    # ==========================================================================

    def render(self, pointer: Dict[str, Union[bool, float, int]]) -> np.ndarray:
        """
        Render full Excalidraw frame and return as uint8 BGR NumPy array for OpenCV compatibility.
        """
        raw_u = float(pointer.get("u", self.width // 2))
        raw_v = float(pointer.get("v", self.height // 2))
        detected = bool(pointer.get("detected", False))

        # 1. Update magnetic snap and hover
        target_u, target_v, _ = self.update_magnetic_snap(raw_u, raw_v, detected)

        # 2. Draw Excalidraw dot grid background
        self.screen_surface.fill(settings.EXCALI_BG)
        dot_spacing = 25
        dot_color = settings.EXCALI_GRID_DOT
        for gx in range(dot_spacing, self.width, dot_spacing):
            for gy in range(dot_spacing, self.height, dot_spacing):
                self.screen_surface.set_at((gx, gy), dot_color)

        # 3. View-specific background contents
        if self.current_view == "MAIN":
            self._render_home_view()
        elif self.current_view == "DRAWING_VIEW":
            self._render_drawing_view()
        elif self.current_view == "LESSON_VIEW":
            self._render_lesson_view()
        elif self.current_view == "IMAGE_VIEW":
            self._render_image_view()
        elif self.current_view == "SETTINGS_VIEW":
            self._render_settings_view()

        # 4. Draw Top floating navigation pill
        self._render_top_pill()

        # 5. Draw Top-Right status pill ("• Suivi actif")
        self._render_tracking_pill(detected)

        # 6. Draw Bottom Toast notification
        self._render_bottom_toast()

        # 7. Draw Click Ripple Waves
        self._render_ripples()

        # 8. Draw Laser Pointer Cursor
        if detected:
            self._render_cursor(target_u, target_v)

        # Convert Pygame RGB Surface to OpenCV BGR NumPy array
        rgb_array = pygame.surfarray.array3d(self.screen_surface)
        bgr_array = np.transpose(rgb_array, (1, 0, 2))[:, :, ::-1].copy()

        return bgr_array

    # Compatibility alias
    render_frame_bgr = render

    def _render_top_pill(self) -> None:
        """Render floating top navigation toolbar with soft shadow and icons."""
        # Shadow
        shadow_rect = self.top_pill_rect.inflate(8, 6).move(0, 4)
        shadow_surf = pygame.Surface((shadow_rect.w, shadow_rect.h), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 16), shadow_surf.get_rect(), border_radius=22)
        self.screen_surface.blit(shadow_surf, shadow_rect.topleft)

        # Main pill
        pygame.draw.rect(self.screen_surface, settings.EXCALI_CARD_BG, self.top_pill_rect, border_radius=18)
        pygame.draw.rect(self.screen_surface, (220, 224, 230), self.top_pill_rect, width=1, border_radius=18)

        for btn in self.nav_buttons:
            # Active highlight or hover expansion
            if btn.is_selected:
                pygame.draw.rect(self.screen_surface, settings.EXCALI_PURPLE_DARK, btn.rect, border_radius=12)
                text_col = settings.COLOR_WHITE
            elif btn.is_hovered:
                pygame.draw.rect(self.screen_surface, settings.EXCALI_PURPLE_LIGHT, btn.rect, border_radius=12)
                text_col = settings.EXCALI_PURPLE_DARK
            else:
                text_col = settings.EXCALI_TEXT_MAIN

            # Draw label
            lbl_surf = self.font_nav.render(btn.label, True, text_col)
            lbl_rect = lbl_surf.get_rect(center=(btn.rect.centerx, btn.rect.bottom - 16))
            self.screen_surface.blit(lbl_surf, lbl_rect)

            # Draw simple geometric icon above label
            self._draw_simple_icon(btn.icon_name, btn.rect.centerx, btn.rect.top + 18, text_col)

    def _draw_simple_icon(self, icon_name: str, cx: int, cy: int, color: Tuple[int, int, int]) -> None:
        """Draw minimalist vector icons."""
        if icon_name == "home":
            pts = [(cx, cy - 8), (cx - 9, cy), (cx + 9, cy)]
            pygame.draw.polygon(self.screen_surface, color, pts)
            pygame.draw.rect(self.screen_surface, color, (cx - 7, cy, 14, 8), 1)
        elif icon_name == "pen":
            pygame.draw.line(self.screen_surface, color, (cx - 7, cy + 7), (cx + 7, cy - 7), 2)
            pygame.draw.circle(self.screen_surface, color, (cx - 7, cy + 7), 2)
        elif icon_name == "eraser":
            rect = pygame.Rect(cx - 7, cy - 5, 14, 10)
            pygame.draw.rect(self.screen_surface, color, rect, 2, border_radius=2)
        elif icon_name == "shapes":
            pygame.draw.circle(self.screen_surface, color, (cx - 5, cy - 3), 4, 1)
            pygame.draw.rect(self.screen_surface, color, (cx, cy, 8, 8), 1)
        elif icon_name == "image":
            rect = pygame.Rect(cx - 8, cy - 6, 16, 12)
            pygame.draw.rect(self.screen_surface, color, rect, 1, border_radius=2)
            pygame.draw.circle(self.screen_surface, color, (cx - 3, cy - 2), 2)
        elif icon_name == "lesson":
            rect = pygame.Rect(cx - 7, cy - 7, 14, 14), 1
            pygame.draw.rect(self.screen_surface, color, (cx - 7, cy - 7, 14, 14), 1, border_radius=2)
            pygame.draw.line(self.screen_surface, color, (cx - 4, cy - 2), (cx + 4, cy - 2), 1)
        elif icon_name == "settings":
            pygame.draw.circle(self.screen_surface, color, (cx, cy), 6, 2)
            for angle in (0, 45, 90, 135):
                rad = math.radians(angle)
                dx, dy = int(9 * math.cos(rad)), int(9 * math.sin(rad))
                pygame.draw.line(self.screen_surface, color, (cx - dx, cy - dy), (cx + dx, cy + dy), 1)

    def _render_tracking_pill(self, detected: bool) -> None:
        """Top-right indicator pill showing tracking status (Mockups 1 & 2)."""
        pill_rect = pygame.Rect(self.width - 170, 24, 145, 42)
        # Background
        pygame.draw.rect(self.screen_surface, settings.EXCALI_CARD_BG, pill_rect, border_radius=14)
        pygame.draw.rect(self.screen_surface, (220, 224, 230), pill_rect, width=1, border_radius=14)

        # Dot
        dot_col = (25, 113, 194) if detected else (230, 100, 30)
        pygame.draw.circle(self.screen_surface, dot_col, (pill_rect.left + 22, pill_rect.centery), 5)

        # Text
        txt = "Suivi actif" if detected else "Recherche..."
        txt_surf = self.font_badge.render(txt, True, settings.EXCALI_TEXT_MAIN)
        self.screen_surface.blit(txt_surf, (pill_rect.left + 36, pill_rect.centery - txt_surf.get_height() // 2))

    def _render_home_view(self) -> None:
        """Render the Excalidraw Home Screen matching Mockup 2."""
        # 1. Title
        title_surf = self.font_title.render("Smart Whiteboard", True, settings.EXCALI_TEXT_MAIN)
        self.screen_surface.blit(title_surf, title_surf.get_rect(center=(self.width // 2, 160)))

        # 2. Subtitle
        sub_surf = self.font_subtitle.render("Pointe avec ta main. Clique avec la télécommande.", True, settings.EXCALI_TEXT_MUTED)
        self.screen_surface.blit(sub_surf, sub_surf.get_rect(center=(self.width // 2, 215)))

        # 3. 4 Action Cards
        for card in self.home_cards:
            rect = card.rect
            # Soft shadow
            shadow_rect = rect.inflate(8, 8).move(0, 3)
            shadow_surf = pygame.Surface((shadow_rect.w, shadow_rect.h), pygame.SRCALPHA)
            pygame.draw.rect(shadow_surf, (0, 0, 0, 14), shadow_surf.get_rect(), border_radius=18)
            self.screen_surface.blit(shadow_surf, shadow_rect.topleft)

            # Card box
            border_col = card.accent_color if card.is_hovered else (45, 45, 45)
            border_thick = 3 if card.is_hovered else 2
            bg_col = settings.EXCALI_PURPLE_LIGHT if card.is_hovered else settings.EXCALI_CARD_BG

            pygame.draw.rect(self.screen_surface, bg_col, rect, border_radius=16)
            pygame.draw.rect(self.screen_surface, border_col, rect, width=border_thick, border_radius=16)

            # Big Icon
            ic_y = rect.top + 60
            self._draw_big_card_icon(card.icon_name, rect.centerx, ic_y, card.accent_color)

            # Card title
            lbl_surf = self.font_card.render(card.label, True, settings.EXCALI_TEXT_MAIN)
            self.screen_surface.blit(lbl_surf, lbl_surf.get_rect(center=(rect.centerx, rect.top + 130)))

            # Card subtitle prompt
            sub_text = "Next pour ouvrir" if card.button_id == "card_draw" else ""
            if sub_text:
                hint_surf = self.font_card_sub.render(sub_text, True, settings.EXCALI_TEXT_MUTED)
                self.screen_surface.blit(hint_surf, hint_surf.get_rect(center=(rect.centerx, rect.top + 165)))

        # 4. Bottom helper badges (Next / Previous)
        badge_y = 620
        # Next Badge
        next_box = pygame.Rect(self.width // 2 - 250, badge_y, 70, 32)
        pygame.draw.rect(self.screen_surface, (25, 25, 25), next_box, border_radius=8)
        nxt_txt = self.font_badge.render("Next", True, settings.COLOR_WHITE)
        self.screen_surface.blit(nxt_txt, nxt_txt.get_rect(center=next_box.center))

        lbl_nxt = self.font_subtitle.render("clic gauche : valider", True, settings.EXCALI_TEXT_MAIN)
        self.screen_surface.blit(lbl_nxt, (next_box.right + 12, next_box.centery - lbl_nxt.get_height() // 2))

        # Previous Badge
        prev_box = pygame.Rect(self.width // 2 + 70, badge_y, 90, 32)
        pygame.draw.rect(self.screen_surface, (25, 25, 25), prev_box, border_radius=8)
        prv_txt = self.font_badge.render("Previous", True, settings.COLOR_WHITE)
        self.screen_surface.blit(prv_txt, prv_txt.get_rect(center=prev_box.center))

        lbl_prv = self.font_subtitle.render("clic droit : retour", True, settings.EXCALI_TEXT_MAIN)
        self.screen_surface.blit(lbl_prv, (prev_box.right + 12, prev_box.centery - lbl_prv.get_height() // 2))

    def _draw_big_card_icon(self, icon_name: str, cx: int, cy: int, color: Tuple[int, int, int]) -> None:
        """Render prominent icons inside home cards."""
        if icon_name == "pen":
            pygame.draw.line(self.screen_surface, color, (cx - 16, cy + 16), (cx + 16, cy - 16), 4)
            pygame.draw.polygon(self.screen_surface, color, [(cx - 20, cy + 20), (cx - 12, cy + 18), (cx - 18, cy + 12)])
        elif icon_name == "image":
            rect = pygame.Rect(cx - 22, cy - 18, 44, 36)
            pygame.draw.rect(self.screen_surface, color, rect, 3, border_radius=4)
            pygame.draw.polygon(self.screen_surface, color, [(cx - 14, cy + 10), (cx - 2, cy - 4), (cx + 8, cy + 10)])
            pygame.draw.circle(self.screen_surface, color, (cx + 8, cy - 6), 4)
        elif icon_name == "lesson":
            rect = pygame.Rect(cx - 20, cy - 18, 40, 36)
            pygame.draw.rect(self.screen_surface, color, rect, 3, border_radius=4)
            pygame.draw.line(self.screen_surface, color, (cx - 12, cy - 6), (cx + 12, cy - 6), 2)
            pygame.draw.line(self.screen_surface, color, (cx - 12, cy + 4), (cx + 12, cy + 4), 2)
        elif icon_name == "settings":
            pygame.draw.circle(self.screen_surface, color, (cx, cy), 12, 3)
            for angle in range(0, 360, 45):
                rad = math.radians(angle)
                x1, y1 = int(cx + 14 * math.cos(rad)), int(cy + 14 * math.sin(rad))
                x2, y2 = int(cx + 19 * math.cos(rad)), int(cy + 19 * math.sin(rad))
                pygame.draw.line(self.screen_surface, color, (x1, y1), (x2, y2), 3)

    def _render_drawing_view(self) -> None:
        """Render the Drawing Screen matching Mockup 1."""
        # 1. Blit user drawings surface
        self.screen_surface.blit(self.drawing_engine.get_surface(), (0, 0))

        # 2. Left Floating Palette
        shadow_rect = self.left_palette_rect.inflate(8, 8).move(0, 4)
        shadow_surf = pygame.Surface((shadow_rect.w, shadow_rect.h), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 16), shadow_surf.get_rect(), border_radius=22)
        self.screen_surface.blit(shadow_surf, shadow_rect.topleft)

        pygame.draw.rect(self.screen_surface, settings.EXCALI_CARD_BG, self.left_palette_rect, border_radius=20)
        pygame.draw.rect(self.screen_surface, (220, 224, 230), self.left_palette_rect, width=1, border_radius=20)

        cx = self.left_palette_rect.centerx
        # 4 Colors
        cy = self.left_palette_rect.top + 36
        for col_id, col_rgb in self.palette_colors:
            is_active = (not self.drawing_engine.is_eraser) and (self.drawing_engine.current_color == col_rgb)
            if is_active:
                pygame.draw.circle(self.screen_surface, settings.EXCALI_PURPLE_LIGHT, (cx, cy), 22)
                pygame.draw.circle(self.screen_surface, settings.EXCALI_PURPLE, (cx, cy), 20, 2)
            pygame.draw.circle(self.screen_surface, col_rgb, (cx, cy), 15)
            cy += 48

        # Divider line
        cy += 4
        pygame.draw.line(self.screen_surface, (220, 224, 230), (cx - 24, cy), (cx + 24, cy), 1)
        cy += 20

        # 3 Thickness bars
        for thick_id, th_px in self.palette_thicknesses:
            is_active = (self.drawing_engine.current_thickness == th_px)
            if is_active:
                th_rect = pygame.Rect(cx - 24, cy - 12, 48, 24)
                pygame.draw.rect(self.screen_surface, settings.EXCALI_PURPLE_LIGHT, th_rect, border_radius=6)
            pygame.draw.line(self.screen_surface, (45, 45, 45), (cx - 16, cy), (cx + 16, cy), max(2, th_px // 2))
            cy += 38

        # Divider line
        cy += 4
        pygame.draw.line(self.screen_surface, (220, 224, 230), (cx - 24, cy), (cx + 24, cy), 1)
        cy += 24

        # Undo icon
        undo_color = settings.EXCALI_PURPLE if len(self.drawing_engine.strokes) > 0 else (180, 180, 180)
        pygame.draw.arc(self.screen_surface, undo_color, (cx - 14, cy - 12, 24, 20), math.radians(45), math.radians(220), 2)
        pygame.draw.polygon(self.screen_surface, undo_color, [(cx - 16, cy - 8), (cx - 9, cy - 14), (cx - 10, cy - 2)])

    def _render_lesson_view(self) -> None:
        """Render Computer Vision teaching lesson sequence."""
        bgr_canvas = np.full((self.height, self.width, 3), 255, dtype=np.uint8)
        self.lesson_viewer.render(bgr_canvas)
        rgb_canvas = bgr_canvas[:, :, ::-1]
        surf = pygame.surfarray.make_surface(np.transpose(rgb_canvas, (1, 0, 2)))
        self.screen_surface.blit(surf, (0, 0))

        # Bottom lesson control pill
        for btn in self.lesson_buttons:
            bg_col = settings.EXCALI_PURPLE_LIGHT if btn.is_hovered else settings.EXCALI_CARD_BG
            pygame.draw.rect(self.screen_surface, bg_col, btn.rect, border_radius=12)
            pygame.draw.rect(self.screen_surface, (200, 205, 215), btn.rect, width=1, border_radius=12)
            txt_surf = self.font_badge.render(btn.label, True, settings.EXCALI_TEXT_MAIN)
            self.screen_surface.blit(txt_surf, txt_surf.get_rect(center=btn.rect.center))

    def _render_image_view(self) -> None:
        """Render image zoom viewer."""
        bgr_canvas = np.full((self.height, self.width, 3), 255, dtype=np.uint8)
        self.zoom_viewer.render(bgr_canvas)
        rgb_canvas = bgr_canvas[:, :, ::-1]
        surf = pygame.surfarray.make_surface(np.transpose(rgb_canvas, (1, 0, 2)))
        self.screen_surface.blit(surf, (0, 0))

        # Bottom image control pill
        for btn in self.image_buttons:
            bg_col = settings.EXCALI_PURPLE_LIGHT if btn.is_hovered else settings.EXCALI_CARD_BG
            pygame.draw.rect(self.screen_surface, bg_col, btn.rect, border_radius=12)
            pygame.draw.rect(self.screen_surface, (200, 205, 215), btn.rect, width=1, border_radius=12)
            txt_surf = self.font_badge.render(btn.label, True, settings.EXCALI_TEXT_MAIN)
            self.screen_surface.blit(txt_surf, txt_surf.get_rect(center=btn.rect.center))

    def _render_settings_view(self) -> None:
        """Render settings and recalibration screen."""
        title_surf = self.font_title.render("Paramètres & Maintenance", True, settings.EXCALI_TEXT_MAIN)
        self.screen_surface.blit(title_surf, title_surf.get_rect(center=(self.width // 2, 160)))

        hint = self.font_subtitle.render("Pour recalibrer la caméra ou réinitialiser le système", True, settings.EXCALI_TEXT_MUTED)
        self.screen_surface.blit(hint, hint.get_rect(center=(self.width // 2, 215)))

        # Big reset card
        for btn in self.settings_buttons:
            rect = btn.rect
            bg_col = settings.EXCALI_PURPLE_LIGHT if btn.is_hovered else settings.EXCALI_CARD_BG
            pygame.draw.rect(self.screen_surface, bg_col, rect, border_radius=18)
            border_col = settings.COLOR_DRAW_RED if btn.button_id == "btn_reset" else settings.COLOR_DRAW_BLACK
            pygame.draw.rect(self.screen_surface, border_col, rect, width=2, border_radius=18)

            txt1 = self.font_card.render(btn.label, True, border_col)
            self.screen_surface.blit(txt1, txt1.get_rect(center=(rect.centerx, rect.top + 45 if rect.h > 80 else rect.centery)))

    def _render_bottom_toast(self) -> None:
        """Render bottom floating toast pill matching Mockup 1."""
        if time.time() > self.toast_timer and self.current_view != "DRAWING_VIEW":
            return

        msg = (
            "Stylo posé · Next pour lever · Previous pour annuler"
            if (self.current_view == "DRAWING_VIEW" and self.drawing_engine.is_pen_down)
            else (
                "Stylo levé (survol) · Next pour poser"
                if self.current_view == "DRAWING_VIEW"
                else self.toast_message
            )
        )

        txt_surf = self.font_toast.render(msg, True, settings.COLOR_WHITE)
        pill_w = txt_surf.get_width() + 48
        pill_h = 44
        pill_rect = pygame.Rect((self.width - pill_w) // 2, self.height - 62, pill_w, pill_h)

        # Shadow
        shadow_rect = pill_rect.inflate(6, 6).move(0, 2)
        shadow_surf = pygame.Surface((shadow_rect.w, shadow_rect.h), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 20), shadow_surf.get_rect(), border_radius=16)
        self.screen_surface.blit(shadow_surf, shadow_rect.topleft)

        # Purple Pill
        pygame.draw.rect(self.screen_surface, settings.EXCALI_PURPLE_DARK, pill_rect, border_radius=14)
        self.screen_surface.blit(txt_surf, txt_surf.get_rect(center=pill_rect.center))

    def _render_ripples(self) -> None:
        """Render expanding click wave ripple feedback."""
        now = time.time()
        remaining_ripples = []

        for rx, ry, st in self.active_ripples:
            elapsed = (now - st) * 1000.0  # ms
            if elapsed < settings.ANIMATION_DURATION_MS:
                progress = elapsed / settings.ANIMATION_DURATION_MS
                radius = int(8 + progress * 32)
                alpha = int(220 * (1.0 - progress))
                rip_surf = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(rip_surf, (*settings.EXCALI_PURPLE, alpha), (radius + 2, radius + 2), radius, 2)
                self.screen_surface.blit(rip_surf, (int(rx) - radius - 2, int(ry) - radius - 2))
                remaining_ripples.append((rx, ry, st))

        self.active_ripples = remaining_ripples

    def _render_cursor(self, u: float, v: float) -> None:
        """Render visible Excalidraw cursor: ring + inner purple dot."""
        iu, iv = int(u), int(v)
        # Outer ring
        pygame.draw.circle(self.screen_surface, (40, 40, 40), (iu, iv), 16, 2)
        # Inner purple dot
        pygame.draw.circle(self.screen_surface, settings.EXCALI_PURPLE, (iu, iv), 5)


# Compatibility alias
WhiteboardInterface = ExcalidrawInterface
