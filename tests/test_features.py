"""
Unit tests for Step 9:
Image Zoom, Lesson Pagination, Annotations, and Global Reset.
"""

import unittest
import numpy as np

from config import settings
from modules.features import ImageZoomViewer, LessonViewer, SystemManager
from modules.drawing import DrawingEngine
from modules.interface import WhiteboardInterface
from modules.interaction import InteractionManager


class TestFeaturesStep9(unittest.TestCase):
    """Test suite for Step 9 Free Functionalities."""

    def test_image_zoom_scaling_and_bounds(self):
        """Verify image zooming in, out, and reset bounds."""
        viewer = ImageZoomViewer()
        self.assertEqual(viewer.zoom_factor, 1.0)

        # Zoom in
        z1 = viewer.zoom_in()
        self.assertGreater(z1, 1.0)

        # Multiple zoom-ins must clamp at ZOOM_MAX
        for _ in range(20):
            viewer.zoom_in()
        self.assertEqual(viewer.zoom_factor, settings.ZOOM_MAX)

        # Reset
        viewer.reset_view()
        self.assertEqual(viewer.zoom_factor, 1.0)

        # Multiple zoom-outs must clamp at ZOOM_MIN
        for _ in range(20):
            viewer.zoom_out()
        self.assertEqual(viewer.zoom_factor, settings.ZOOM_MIN)

    def test_lesson_pagination_and_bounds(self):
        """Verify coherent lesson pagination (Page 1 -> 2 -> 3) and bounds."""
        lesson = LessonViewer()
        self.assertEqual(lesson.current_page, 1)

        # Page 1 -> Page 2
        p2 = lesson.next_page()
        self.assertEqual(p2, 2)

        # Page 2 -> Page 3
        p3 = lesson.next_page()
        self.assertEqual(p3, 3)

        # Cannot exceed total pages
        p_extra = lesson.next_page()
        self.assertEqual(p_extra, 3)

        # Page 3 -> Page 2
        p_prev = lesson.prev_page()
        self.assertEqual(p_prev, 2)

        # Reset lesson
        lesson.reset_lesson()
        self.assertEqual(lesson.current_page, 1)

    def test_global_system_reset(self):
        """Verify that global reset restores drawings, lesson, and zoom to initial state."""
        ui = WhiteboardInterface()
        interaction = InteractionManager(ui)

        # Modify states: draw stroke, zoom in, navigate lesson
        ui.drawing_engine.set_pen_state(True)
        ui.drawing_engine.add_point(100, 100)
        ui.drawing_engine.set_pen_state(False)
        self.assertEqual(len(ui.drawing_engine.strokes), 1)

        ui.zoom_viewer.zoom_in()
        self.assertGreater(ui.zoom_viewer.zoom_factor, 1.0)

        ui.lesson_viewer.next_page()
        self.assertEqual(ui.lesson_viewer.current_page, 2)

        # Trigger Global Reset via interaction
        ui.set_view("SETTINGS_VIEW")
        action = interaction._handle_button_action("set_reset")

        self.assertEqual(action, "GLOBAL_RESET")
        self.assertEqual(len(ui.drawing_engine.strokes), 0)
        self.assertEqual(ui.zoom_viewer.zoom_factor, 1.0)
        self.assertEqual(ui.lesson_viewer.current_page, 1)
        self.assertEqual(ui.current_view, "MAIN")


if __name__ == "__main__":
    unittest.main()
