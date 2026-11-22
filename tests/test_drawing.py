"""
Unit tests for Step 8:
Custom Bresenham line algorithm, thick brush rasterization,
Stroke objects, Undo/Redo stacks, and canvas operations.
"""

import unittest
import numpy as np

from config import settings
from modules.drawing import (
    bresenham_line,
    draw_thick_segment_custom,
    DrawingEngine,
    Stroke,
)


class TestDrawingStep8(unittest.TestCase):
    """Test suite for Step 8 Bresenham line drawing and engine mechanics."""

    def test_bresenham_cardinal_and_diagonal_directions(self):
        """Verify Bresenham algorithm generates continuous connected points across all directions."""
        # 1. Horizontal segment (dx = 10, dy = 0)
        h_pts = bresenham_line(0, 0, 10, 0)
        self.assertEqual(len(h_pts), 11)
        self.assertEqual(h_pts[0], (0, 0))
        self.assertEqual(h_pts[-1], (10, 0))

        # 2. Vertical segment (dx = 0, dy = 10)
        v_pts = bresenham_line(5, 5, 5, 15)
        self.assertEqual(len(v_pts), 11)
        self.assertEqual(v_pts[0], (5, 5))
        self.assertEqual(v_pts[-1], (5, 15))

        # 3. Diagonal segment (45 degrees)
        d_pts = bresenham_line(0, 0, 10, 10)
        self.assertEqual(len(d_pts), 11)

        # 4. Negative slopes (all 8 octants symmetry)
        rev_pts = bresenham_line(10, 10, 0, 0)
        self.assertEqual(len(rev_pts), 11)
        self.assertEqual(rev_pts[0], (10, 10))
        self.assertEqual(rev_pts[-1], (0, 0))

    def test_thick_segment_custom_rendering(self):
        """Verify that custom thick segment modifies canvas pixels with selected color."""
        canvas = np.zeros((100, 100, 3), dtype=np.uint8)
        color = (0, 255, 0)  # Green

        draw_thick_segment_custom(canvas, 20, 20, 60, 20, color, thickness=6)

        # Pixels on the segment centerline must be green
        np.testing.assert_array_equal(canvas[20, 40], color)
        # Pixels within brush radius (R=3) must also be green
        np.testing.assert_array_equal(canvas[22, 40], color)
        # Distant pixels must remain untouched (black)
        np.testing.assert_array_equal(canvas[50, 40], [0, 0, 0])

    def test_drawing_engine_pen_toggle_and_strokes(self):
        """Verify Pen Up / Pen Down toggle and continuous stroke recording."""
        engine = DrawingEngine(width=200, height=200)

        self.assertFalse(engine.is_pen_down)
        # Adding point while pen is UP must not draw
        engine.add_point(50, 50)
        self.assertEqual(len(engine.strokes), 0)

        # Toggle pen DOWN
        engine.toggle_pen()
        self.assertTrue(engine.is_pen_down)

        # Add trajectory points
        engine.add_point(50, 50)
        engine.add_point(60, 60)
        engine.add_point(70, 70)

        # Lift pen UP
        engine.toggle_pen()
        self.assertFalse(engine.is_pen_down)
        self.assertEqual(len(engine.strokes), 1)
        self.assertEqual(len(engine.strokes[0].points), 3)

    def test_undo_and_redo_stacks(self):
        """Verify Undo removes the last stroke and Redo restores it correctly."""
        engine = DrawingEngine(width=200, height=200)

        # Draw Stroke 1
        engine.set_pen_state(True)
        engine.add_point(10, 10)
        engine.add_point(20, 20)
        engine.set_pen_state(False)

        # Draw Stroke 2
        engine.set_pen_state(True)
        engine.add_point(50, 50)
        engine.add_point(60, 60)
        engine.set_pen_state(False)

        self.assertEqual(len(engine.strokes), 2)
        self.assertEqual(len(engine.redo_stack), 0)

        # Undo Stroke 2
        success_undo = engine.undo()
        self.assertTrue(success_undo)
        self.assertEqual(len(engine.strokes), 1)
        self.assertEqual(len(engine.redo_stack), 1)

        # Redo Stroke 2
        success_redo = engine.redo()
        self.assertTrue(success_redo)
        self.assertEqual(len(engine.strokes), 2)
        self.assertEqual(len(engine.redo_stack), 0)

    def test_clear_canvas(self):
        """Verify clear() wipes all strokes and restores clean background."""
        engine = DrawingEngine(width=100, height=100, bg_color=(255, 255, 255))
        engine.set_pen_state(True)
        engine.add_point(10, 10)
        engine.add_point(30, 30)
        engine.set_pen_state(False)

        self.assertEqual(len(engine.strokes), 1)
        engine.clear()

        self.assertEqual(len(engine.strokes), 0)
        self.assertEqual(len(engine.redo_stack), 0)
        # Whole canvas must be background color
        self.assertTrue(np.all(engine.canvas == 255))


if __name__ == "__main__":
    unittest.main()
