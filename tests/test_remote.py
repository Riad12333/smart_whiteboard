"""
Unit tests for Step 6:
Remote button scancode translation, debounce anti-repeat timing, and exchange contract.
"""

import time
import unittest

from config import settings
from modules.remote import RemoteHandler


class TestRemoteStep6(unittest.TestCase):
    """Test suite for Step 6 remote control event generation."""

    def test_left_click_mappings(self):
        """Verify that Next / Right Arrow / Page Down emit 'LEFT_CLICK'."""
        remote = RemoteHandler(debounce_sec=0.01)

        # Right Arrow (Windows: 2555904)
        evt1 = remote.process_key(2555904)
        self.assertEqual(evt1, "LEFT_CLICK")
        time.sleep(0.02)

        # Page Down (Windows: 2228224)
        evt2 = remote.process_key(2228224)
        self.assertEqual(evt2, "LEFT_CLICK")
        time.sleep(0.02)

        # Key 'n' (Next simulation)
        evt3 = remote.process_key(ord("n"))
        self.assertEqual(evt3, "LEFT_CLICK")

    def test_right_click_mappings(self):
        """Verify that Prev / Left Arrow / Page Up emit 'RIGHT_CLICK'."""
        remote = RemoteHandler(debounce_sec=0.01)

        # Left Arrow (Windows: 2490368)
        evt1 = remote.process_key(2490368)
        self.assertEqual(evt1, "RIGHT_CLICK")
        time.sleep(0.02)

        # Page Up (Windows: 2162688)
        evt2 = remote.process_key(2162688)
        self.assertEqual(evt2, "RIGHT_CLICK")
        time.sleep(0.02)

        # Key 'p' (Previous simulation)
        evt3 = remote.process_key(ord("p"))
        self.assertEqual(evt3, "RIGHT_CLICK")

    def test_debounce_anti_repeat(self):
        """Verify that holding down a button does not generate multiple clicks within debounce window."""
        debounce_sec = 0.20  # 200 ms
        remote = RemoteHandler(debounce_sec=debounce_sec)

        # First press: must trigger LEFT_CLICK
        first_evt = remote.process_key(2555904)
        self.assertEqual(first_evt, "LEFT_CLICK")

        # Rapid succession (simulating OS auto-repeat after 50 ms): must be suppressed (None)
        time.sleep(0.05)
        repeat_evt = remote.process_key(2555904)
        self.assertIsNone(repeat_evt, "Rapid repeat within debounce window must return None.")

        # After debounce window expires: must trigger again
        time.sleep(0.22)
        valid_evt = remote.process_key(2555904)
        self.assertEqual(valid_evt, "LEFT_CLICK")

    def test_unmapped_keys_return_none(self):
        """Verify that random unmapped keys return None and do not trigger clicks."""
        remote = RemoteHandler()
        self.assertIsNone(remote.process_key(ord("z")))
        self.assertIsNone(remote.process_key(ord("1")))
        self.assertIsNone(remote.process_key(-1))

    def test_exchange_format_contract(self):
        """Ensure that output strictly belongs to {'LEFT_CLICK', 'RIGHT_CLICK', None}."""
        remote = RemoteHandler(debounce_sec=0.0)
        allowed_events = {"LEFT_CLICK", "RIGHT_CLICK", None}

        self.assertIn(remote.process_key(2555904), allowed_events)
        self.assertIn(remote.process_key(2490368), allowed_events)
        self.assertIn(remote.process_key(-1), allowed_events)


if __name__ == "__main__":
    unittest.main()
