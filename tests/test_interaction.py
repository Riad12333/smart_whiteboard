"""
Unit tests for Step 7:
Interface button hit testing, menu navigation hierarchy, and interaction dispatching.
"""

import unittest

from config import settings
from modules.interface import Button, WhiteboardInterface
from modules.interaction import InteractionManager


class TestInteractionStep7(unittest.TestCase):
    """Test suite for Step 7 GUI and Interaction logic."""

    def test_button_hit_testing(self):
        """Verify Button.contains() correctly identifies inside and outside points."""
        btn = Button("test_btn", "Test", x=100, y=100, width=200, height=50)

        # Inside points
        self.assertTrue(btn.contains(150, 125))
        self.assertTrue(btn.contains(100, 100))  # Top-left corner
        self.assertTrue(btn.contains(300, 150))  # Bottom-right corner

        # Outside points
        self.assertFalse(btn.contains(99, 125))
        self.assertFalse(btn.contains(301, 125))
        self.assertFalse(btn.contains(150, 99))
        self.assertFalse(btn.contains(150, 151))

    def test_menu_hierarchy_and_navigation(self):
        """Verify navigation from Main Menu -> Submenus -> Retour Menu."""
        ui = WhiteboardInterface()
        interaction = InteractionManager(ui)

        self.assertEqual(ui.current_view, "MAIN")

        # Simulate clicking on "Dessiner" card (centered on card_draw)
        cx = ui.home_cards[0].rect.centerx
        cy = ui.home_cards[0].rect.centery
        pointer_on_draw = {"detected": True, "u": float(cx), "v": float(cy)}
        action = interaction.process_interaction(pointer_on_draw, "LEFT_CLICK")

        self.assertEqual(action, "OPEN_DRAWING")
        self.assertEqual(ui.current_view, "DRAWING_VIEW")

        # In DRAWING_VIEW, simulate clicking on "Accueil" nav button
        nx = ui.nav_buttons[0].rect.centerx
        ny = ui.nav_buttons[0].rect.centery
        pointer_on_back = {"detected": True, "u": float(nx), "v": float(ny)}
        back_action = interaction.process_interaction(pointer_on_back, "LEFT_CLICK")

        self.assertEqual(back_action, "BACK_TO_MAIN")
        self.assertEqual(ui.current_view, "MAIN")

    def test_right_click_universal_back(self):
        """Verify that RIGHT_CLICK immediately returns to MAIN menu from any submenu."""
        ui = WhiteboardInterface()
        interaction = InteractionManager(ui)

        ui.set_view("LESSON_VIEW")
        self.assertEqual(ui.current_view, "LESSON_VIEW")

        pointer = {"detected": True, "u": 100.0, "v": 100.0}
        action = interaction.process_interaction(pointer, "RIGHT_CLICK")

        self.assertEqual(action, "BACK_TO_MAIN")
        self.assertEqual(ui.current_view, "MAIN")

    def test_reset_action(self):
        """Verify settings reset action."""
        ui = WhiteboardInterface()
        interaction = InteractionManager(ui)

        ui.set_view("SETTINGS_VIEW")
        rx = ui.settings_buttons[0].rect.centerx
        ry = ui.settings_buttons[0].rect.centery
        pointer_on_reset = {"detected": True, "u": float(rx), "v": float(ry)}
        action = interaction.process_interaction(pointer_on_reset, "LEFT_CLICK")

        self.assertEqual(action, "GLOBAL_RESET")
        self.assertEqual(ui.current_view, "MAIN")


if __name__ == "__main__":
    unittest.main()
