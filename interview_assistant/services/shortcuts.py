"""Global keyboard shortcuts."""

import threading
from typing import Callable, Dict, Optional

from interview_assistant.core.config import get_config
from interview_assistant.core.events import Event, get_event_bus


class ShortcutManager:
    """
    Manages global keyboard shortcuts.

    Uses pynput for cross-desktop environment support.
    """

    def __init__(self):
        """Initialize shortcut manager."""
        self._config = get_config()
        self._event_bus = get_event_bus()

        self._listener = None
        self._callbacks: Dict[str, Callable] = {}
        self._current_keys = set()

        # Register default shortcuts
        self._shortcuts = {
            "toggle_recording": self._parse_shortcut(self._config.shortcuts.toggle_recording),
            "toggle_window": self._parse_shortcut(self._config.shortcuts.toggle_window),
            "clear_history": self._parse_shortcut(self._config.shortcuts.clear_history),
            "copy_answer": self._parse_shortcut(self._config.shortcuts.copy_answer),
        }

    def _parse_shortcut(self, shortcut_str: str) -> set:
        """
        Parse a GTK-style shortcut string into key set.

        Args:
            shortcut_str: Shortcut like "<Control><Alt>r"

        Returns:
            Set of key names
        """
        keys = set()

        # Parse modifiers
        if "<Control>" in shortcut_str or "<Ctrl>" in shortcut_str:
            keys.add("ctrl")
        if "<Alt>" in shortcut_str:
            keys.add("alt")
        if "<Shift>" in shortcut_str:
            keys.add("shift")
        if "<Super>" in shortcut_str or "<Meta>" in shortcut_str:
            keys.add("cmd")

        # Parse the main key
        import re
        main_key = re.sub(r'<[^>]+>', '', shortcut_str).lower()
        if main_key:
            keys.add(main_key)

        return keys

    def start(self) -> bool:
        """
        Start listening for global shortcuts.

        Returns:
            True if started successfully
        """
        try:
            from pynput import keyboard

            def on_press(key):
                try:
                    # Get key name
                    if hasattr(key, 'char') and key.char:
                        key_name = key.char.lower()
                    elif hasattr(key, 'name'):
                        key_name = key.name.lower()
                        # Map pynput names to our names
                        name_map = {
                            'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl',
                            'alt_l': 'alt', 'alt_r': 'alt',
                            'shift_l': 'shift', 'shift_r': 'shift',
                            'cmd': 'cmd', 'cmd_l': 'cmd', 'cmd_r': 'cmd',
                        }
                        key_name = name_map.get(key_name, key_name)
                    else:
                        return

                    self._current_keys.add(key_name)

                    # Check for matches
                    self._check_shortcuts()

                except Exception:
                    pass

            def on_release(key):
                try:
                    if hasattr(key, 'char') and key.char:
                        key_name = key.char.lower()
                    elif hasattr(key, 'name'):
                        key_name = key.name.lower()
                        name_map = {
                            'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl',
                            'alt_l': 'alt', 'alt_r': 'alt',
                            'shift_l': 'shift', 'shift_r': 'shift',
                            'cmd': 'cmd', 'cmd_l': 'cmd', 'cmd_r': 'cmd',
                        }
                        key_name = name_map.get(key_name, key_name)
                    else:
                        return

                    self._current_keys.discard(key_name)

                except Exception:
                    pass

            self._listener = keyboard.Listener(
                on_press=on_press,
                on_release=on_release,
            )
            self._listener.start()

            return True

        except ImportError:
            print("pynput not installed. Global shortcuts disabled.")
            return False
        except Exception as e:
            print(f"Error starting shortcut listener: {e}")
            return False

    def stop(self) -> None:
        """Stop listening for shortcuts."""
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _check_shortcuts(self) -> None:
        """Check if current keys match any shortcut."""
        for name, keys in self._shortcuts.items():
            if keys and keys.issubset(self._current_keys):
                self._trigger_shortcut(name)
                # Clear to prevent repeated triggering
                self._current_keys.clear()
                break

    def _trigger_shortcut(self, name: str) -> None:
        """
        Trigger a shortcut callback.

        Args:
            name: Shortcut name
        """
        # Emit event
        if name == "toggle_recording":
            self._event_bus.emit(Event.RECORDING_STARTED if not self._is_recording() else Event.RECORDING_STOPPED)
        elif name == "toggle_window":
            self._event_bus.emit(Event.WINDOW_VISIBILITY_CHANGED)
        elif name == "clear_history":
            self._event_bus.emit(Event.HISTORY_CLEARED)

        # Call registered callback
        if name in self._callbacks:
            try:
                self._callbacks[name]()
            except Exception as e:
                print(f"Error in shortcut callback: {e}")

    def _is_recording(self) -> bool:
        """Check if currently recording (placeholder)."""
        return False

    def register_callback(self, shortcut_name: str, callback: Callable) -> None:
        """
        Register a callback for a shortcut.

        Args:
            shortcut_name: Name of the shortcut
            callback: Function to call when triggered
        """
        self._callbacks[shortcut_name] = callback

    def set_shortcut(self, name: str, shortcut_str: str) -> None:
        """
        Set a new shortcut.

        Args:
            name: Shortcut name
            shortcut_str: GTK-style shortcut string
        """
        self._shortcuts[name] = self._parse_shortcut(shortcut_str)

    @property
    def is_running(self) -> bool:
        """Check if listener is running."""
        return self._listener is not None and self._listener.is_alive()


# Global shortcut manager
_shortcut_manager: Optional[ShortcutManager] = None


def get_shortcut_manager() -> ShortcutManager:
    """Get the global shortcut manager."""
    global _shortcut_manager
    if _shortcut_manager is None:
        _shortcut_manager = ShortcutManager()
    return _shortcut_manager
