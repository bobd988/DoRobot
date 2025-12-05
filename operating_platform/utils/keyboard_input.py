"""
Terminal-based keyboard input for headless systems.

This module provides non-blocking keyboard input that works in terminal
without requiring a GUI or OpenCV window. Used when SHOW=0.
"""

import sys
import select
import logging

# Platform-specific imports
try:
    import termios
    import tty
    _TERMIOS_AVAILABLE = True
except ImportError:
    _TERMIOS_AVAILABLE = False


class TerminalKeyboard:
    """
    Non-blocking keyboard reader for terminal/headless mode.

    Works on Linux/macOS terminals without GUI.
    Uses termios to read raw keyboard input.
    """

    def __init__(self):
        self._old_settings = None
        self._initialized = False

        if not _TERMIOS_AVAILABLE:
            logging.warning("[TerminalKeyboard] termios not available (Windows?), keyboard input disabled")
            return

        if not sys.stdin.isatty():
            logging.warning("[TerminalKeyboard] stdin is not a TTY, keyboard input disabled")
            return

    def start(self):
        """Initialize terminal for raw input mode."""
        if not _TERMIOS_AVAILABLE or not sys.stdin.isatty():
            return False

        try:
            self._old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
            self._initialized = True
            logging.info("[TerminalKeyboard] Terminal keyboard input enabled")
            logging.info("[TerminalKeyboard] Press 'n' to save, 'p' to proceed, 'e' to exit")
            return True
        except Exception as e:
            logging.warning(f"[TerminalKeyboard] Failed to initialize: {e}")
            return False

    def stop(self):
        """Restore terminal to normal mode."""
        if self._old_settings is not None:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
                self._initialized = False
            except Exception:
                pass

    def get_key(self, timeout_ms: int = 10) -> int:
        """
        Non-blocking read of a single keypress.

        Args:
            timeout_ms: Timeout in milliseconds (like cv2.waitKey)

        Returns:
            Key code (ord value) or -1 if no key pressed.
            Compatible with cv2.waitKey() return values.
        """
        if not self._initialized:
            return -1

        try:
            # Convert ms to seconds for select
            timeout_s = timeout_ms / 1000.0

            # Check if input is available
            ready, _, _ = select.select([sys.stdin], [], [], timeout_s)

            if ready:
                char = sys.stdin.read(1)
                if char:
                    return ord(char)

            return -1

        except Exception:
            return -1

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


# Global instance for convenience
_terminal_keyboard = None


def init_terminal_keyboard():
    """Initialize global terminal keyboard instance."""
    global _terminal_keyboard
    if _terminal_keyboard is None:
        _terminal_keyboard = TerminalKeyboard()
        _terminal_keyboard.start()
    return _terminal_keyboard


def stop_terminal_keyboard():
    """Stop and cleanup terminal keyboard."""
    global _terminal_keyboard
    if _terminal_keyboard is not None:
        _terminal_keyboard.stop()
        _terminal_keyboard = None


def get_key_headless(timeout_ms: int = 10) -> int:
    """
    Get key press in headless mode.

    This is a drop-in replacement for cv2.waitKey() when no GUI is available.

    Args:
        timeout_ms: Timeout in milliseconds

    Returns:
        Key code or -1 if no key pressed
    """
    global _terminal_keyboard
    if _terminal_keyboard is None:
        init_terminal_keyboard()
    return _terminal_keyboard.get_key(timeout_ms)
