"""Event bus for inter-component communication."""

import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional
from enum import Enum, auto

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib


class Event(Enum):
    """Application events."""
    # Audio events
    AUDIO_LEVEL = auto()
    AUDIO_CHUNK = auto()
    AUDIO_DEVICE_CHANGED = auto()

    # Transcription events
    TRANSCRIPTION_STARTED = auto()
    TRANSCRIPTION_PARTIAL = auto()
    TRANSCRIPTION_COMPLETE = auto()
    TRANSCRIPTION_ERROR = auto()

    # AI events
    AI_REQUEST_STARTED = auto()
    AI_TOKEN_RECEIVED = auto()
    AI_RESPONSE_COMPLETE = auto()
    AI_ERROR = auto()

    # Session events
    SESSION_STARTED = auto()
    SESSION_ENDED = auto()
    INTERVIEW_TYPE_CHANGED = auto()

    # UI events
    WINDOW_VISIBILITY_CHANGED = auto()
    STEALTH_MODE_CHANGED = auto()
    THEME_CHANGED = auto()

    # Recording events
    RECORDING_STARTED = auto()
    RECORDING_STOPPED = auto()
    RECORDING_PAUSED = auto()

    # History events
    HISTORY_UPDATED = auto()
    HISTORY_CLEARED = auto()


class EventBus:
    """
    Thread-safe pub/sub event system.

    Integrates with GLib main loop to ensure UI updates
    happen on the main thread.
    """

    def __init__(self):
        self._subscribers: Dict[Event, List[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
        self._enabled = True

    def subscribe(self, event: Event, callback: Callable[[Any], None]) -> None:
        """
        Subscribe to an event.

        Args:
            event: The event to subscribe to
            callback: Function to call when event is emitted
        """
        with self._lock:
            if callback not in self._subscribers[event]:
                self._subscribers[event].append(callback)

    def unsubscribe(self, event: Event, callback: Callable[[Any], None]) -> None:
        """
        Unsubscribe from an event.

        Args:
            event: The event to unsubscribe from
            callback: The callback to remove
        """
        with self._lock:
            if callback in self._subscribers[event]:
                self._subscribers[event].remove(callback)

    def emit(self, event: Event, data: Any = None, on_main_thread: bool = True) -> None:
        """
        Emit an event to all subscribers.

        Args:
            event: The event to emit
            data: Optional data to pass to subscribers
            on_main_thread: If True, schedule callbacks on GTK main thread
        """
        if not self._enabled:
            return

        with self._lock:
            callbacks = self._subscribers[event].copy()

        for callback in callbacks:
            if on_main_thread:
                GLib.idle_add(self._safe_callback, callback, data)
            else:
                self._safe_callback(callback, data)

    def _safe_callback(self, callback: Callable, data: Any) -> bool:
        """Safely execute callback, catching exceptions."""
        try:
            callback(data)
        except Exception as e:
            print(f"Error in event callback: {e}")
        return False  # Don't repeat GLib.idle_add

    def enable(self) -> None:
        """Enable event emission."""
        self._enabled = True

    def disable(self) -> None:
        """Disable event emission (useful during shutdown)."""
        self._enabled = False

    def clear(self) -> None:
        """Remove all subscribers."""
        with self._lock:
            self._subscribers.clear()


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
