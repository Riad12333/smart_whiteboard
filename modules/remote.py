"""
Remote control event listener, debouncing, and keyboard mapping module (Step 6).
Maps physical presentation clicker buttons or keyboard simulation keys to standard click events:
  - "Next"     -> "LEFT_CLICK"
  - "Previous" -> "RIGHT_CLICK"
Part of the Smart Interactive Whiteboard project (USTHB 2026-2027).

NOTE: The anti-repeat debounce timer, scancode mapping table, and event dispatching
are implemented from scratch in Python. OpenCV's cv2.waitKeyEx() is used exclusively
to read extended keyboard/HID input scancodes from the window message queue.
"""

import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from config import settings


class RemoteHandler:
    """
    Translates raw keyboard or presentation remote keycodes into standard events:
    "LEFT_CLICK" | "RIGHT_CLICK" | None, with configurable anti-repeat debounce.
    """

    def __init__(
        self,
        debounce_sec: float = settings.REMOTE_DEBOUNCE_SEC,
        next_keycodes: Optional[List[int]] = None,
        prev_keycodes: Optional[List[int]] = None,
    ):
        self.debounce_sec = debounce_sec
        self.next_keycodes = set(
            settings.REMOTE_NEXT_KEYCODES if next_keycodes is None else next_keycodes
        )
        self.prev_keycodes = set(
            settings.REMOTE_PREV_KEYCODES if prev_keycodes is None else prev_keycodes
        )

        self._last_event_time: float = 0.0
        self._last_event: Optional[str] = None
        self._last_raw_keycode: int = -1

    def process_key(self, raw_keycode: int) -> Optional[str]:
        """
        Process a raw keycode (from cv2.waitKeyEx or keyboard event).
        Returns:
          "LEFT_CLICK"  : When Next / Right Arrow / Page Down is pressed.
          "RIGHT_CLICK" : When Previous / Left Arrow / Page Up is pressed.
          None          : When no relevant key is pressed or event is within debounce period.
        """
        # No key pressed
        if raw_keycode in (-1, 255, 0):
            return None

        self._last_raw_keycode = raw_keycode
        now = time.perf_counter()

        # Check for Next / Left-click triggers
        if raw_keycode in self.next_keycodes:
            if (now - self._last_event_time) >= self.debounce_sec:
                self._last_event_time = now
                self._last_event = "LEFT_CLICK"
                return "LEFT_CLICK"
            return None

        # Check for Previous / Right-click triggers
        if raw_keycode in self.prev_keycodes:
            if (now - self._last_event_time) >= self.debounce_sec:
                self._last_event_time = now
                self._last_event = "RIGHT_CLICK"
                return "RIGHT_CLICK"
            return None

        return None

    def add_custom_keycode(self, keycode: int, action: str) -> None:
        """Dynamically register a newly discovered hardware remote keycode."""
        if action == "LEFT_CLICK":
            self.next_keycodes.add(keycode)
        elif action == "RIGHT_CLICK":
            self.prev_keycodes.add(keycode)

    def get_last_event(self) -> Optional[str]:
        """Return the most recently generated event."""
        return self._last_event

    def get_last_raw_keycode(self) -> int:
        """Return the raw integer value of the last pressed key."""
        return self._last_raw_keycode

    def reset(self) -> None:
        """Reset debounce timer and state."""
        self._last_event_time = 0.0
        self._last_event = None
        self._last_raw_keycode = -1


def run_remote_identifier() -> None:
    """
    Interactive diagnostic tool to identify actual keycodes emitted by
    a physical presentation remote or keyboard simulation keys (Step 6).
    """
    remote = RemoteHandler()
    window_name = "Remote Key Identifier - Step 6 (Press remote or keyboard keys)"
    canvas = np.zeros((450, 750, 3), dtype=np.uint8)

    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    history: List[str] = []
    print("\n================ Remote Key Identifier ================")
    print(" Press any button on your physical remote or keyboard:")
    print("   - Next / Right Arrow / Page Down -> LEFT_CLICK")
    print("   - Prev / Left Arrow  / Page Up   -> RIGHT_CLICK")
    print(" [q] or [ESC] : Exit")
    print("=======================================================\n")

    try:
        while True:
            canvas[:] = (25, 25, 25)

            # Draw header
            cv2.rectangle(canvas, (10, 10), (740, 60), (45, 45, 45), -1)
            cv2.putText(
                canvas,
                "Presentation Remote / Key Code Identifier",
                (25, 42),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                settings.COLOR_WHITE,
                2,
                cv2.LINE_AA,
            )

            # Instructions
            cv2.putText(
                canvas,
                "Press any key on remote or keyboard. Press 'q' to quit.",
                (25, 95),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                settings.COLOR_CYAN,
                1,
                cv2.LINE_AA,
            )

            # Draw event log
            cv2.putText(
                canvas,
                "Recent Events Log:",
                (25, 140),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                settings.COLOR_YELLOW,
                1,
                cv2.LINE_AA,
            )

            y_offset = 175
            for entry in history[-7:]:
                cv2.putText(
                    canvas,
                    entry,
                    (35, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.52,
                    settings.COLOR_GREEN if "LEFT_CLICK" in entry else (
                        settings.COLOR_MAGENTA if "RIGHT_CLICK" in entry else settings.COLOR_WHITE
                    ),
                    1,
                    cv2.LINE_AA,
                )
                y_offset += 32

            cv2.imshow(window_name, canvas)

            # Wait for key using waitKeyEx to capture extended 32-bit scancodes
            key = cv2.waitKeyEx(50)

            if key not in (-1, 255, 0):
                if key in (ord("q"), ord("Q"), 27):
                    break

                event = remote.process_key(key)
                hex_str = f"0x{key:X}"
                char_repr = chr(key) if (32 <= key <= 126) else "SPECIAL"

                if event == "LEFT_CLICK":
                    log_line = f"[MATCH] Code: {key:8d} ({hex_str:8s}) -> LEFT_CLICK (Next)"
                elif event == "RIGHT_CLICK":
                    log_line = f"[MATCH] Code: {key:8d} ({hex_str:8s}) -> RIGHT_CLICK (Prev)"
                else:
                    log_line = f"[INFO]  Code: {key:8d} ({hex_str:8s}) -> Key: '{char_repr}' (Debounced or Unmapped)"

                print(log_line)
                history.append(log_line)

    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run_remote_identifier()
