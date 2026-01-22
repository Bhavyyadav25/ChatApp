"""Status indicator widget."""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from interview_assistant.core.events import Event, get_event_bus


class StatusIndicator(Gtk.Box):
    """
    Status indicator showing current state.

    Shows recording, processing, or idle state.
    """

    class State:
        IDLE = "idle"
        RECORDING = "recording"
        PROCESSING = "processing"
        ACTIVE = "active"
        ERROR = "error"

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._state = self.State.IDLE

        # Status dot
        self._dot = Gtk.Box()
        self._dot.set_size_request(10, 10)
        self._dot.add_css_class("status-indicator")

        # Status label
        self._label = Gtk.Label(label="Ready")
        self._label.add_css_class("text-secondary")

        self.append(self._dot)
        self.append(self._label)

        # Subscribe to events
        self._event_bus = get_event_bus()
        self._event_bus.subscribe(Event.RECORDING_STARTED, lambda _: self.set_state(self.State.RECORDING))
        self._event_bus.subscribe(Event.RECORDING_STOPPED, lambda _: self.set_state(self.State.IDLE))
        self._event_bus.subscribe(Event.AI_REQUEST_STARTED, lambda _: self.set_state(self.State.PROCESSING))
        self._event_bus.subscribe(Event.AI_RESPONSE_COMPLETE, lambda _: self.set_state(self.State.ACTIVE))
        self._event_bus.subscribe(Event.AI_ERROR, lambda _: self.set_state(self.State.ERROR))

    def set_state(self, state: str) -> None:
        """
        Set the indicator state.

        Args:
            state: One of State constants
        """
        self._state = state

        # Remove old classes
        for cls in ["active", "recording", "processing", "error"]:
            self._dot.remove_css_class(cls)

        # Set new state
        labels = {
            self.State.IDLE: "Ready",
            self.State.RECORDING: "Recording...",
            self.State.PROCESSING: "Processing...",
            self.State.ACTIVE: "Active",
            self.State.ERROR: "Error",
        }

        self._label.set_label(labels.get(state, "Unknown"))

        if state != self.State.IDLE:
            self._dot.add_css_class(state)

    @property
    def state(self) -> str:
        """Get current state."""
        return self._state


class RecordButton(Gtk.ToggleButton):
    """
    Recording toggle button with visual feedback.
    """

    def __init__(self):
        super().__init__()

        self._recording = False

        # Icon
        self._icon = Gtk.Image.new_from_icon_name("media-record-symbolic")
        self.set_child(self._icon)

        self.add_css_class("record-button")
        self.set_tooltip_text("Start/Stop Recording")

        # Connect toggle
        self.connect("toggled", self._on_toggled)

        # Subscribe to events
        self._event_bus = get_event_bus()
        self._event_bus.subscribe(Event.RECORDING_STARTED, self._on_recording_started)
        self._event_bus.subscribe(Event.RECORDING_STOPPED, self._on_recording_stopped)

    def _on_toggled(self, button) -> None:
        """Handle button toggle."""
        if self.get_active():
            self._icon.set_from_icon_name("media-playback-stop-symbolic")
        else:
            self._icon.set_from_icon_name("media-record-symbolic")

    def _on_recording_started(self, _) -> None:
        """Handle recording started event."""
        if not self.get_active():
            self.set_active(True)

    def _on_recording_stopped(self, _) -> None:
        """Handle recording stopped event."""
        if self.get_active():
            self.set_active(False)

    @property
    def is_recording(self) -> bool:
        """Check if recording."""
        return self.get_active()


class ProcessingSpinner(Gtk.Box):
    """
    Processing indicator with spinner and label.
    """

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._spinner = Gtk.Spinner()
        self._label = Gtk.Label(label="Processing...")
        self._label.add_css_class("text-muted")

        self.append(self._spinner)
        self.append(self._label)

        self.set_visible(False)

        # Subscribe to events
        self._event_bus = get_event_bus()
        self._event_bus.subscribe(Event.AI_REQUEST_STARTED, lambda _: self.start())
        self._event_bus.subscribe(Event.AI_RESPONSE_COMPLETE, lambda _: self.stop())
        self._event_bus.subscribe(Event.AI_ERROR, lambda _: self.stop())

    def start(self, message: str = "Processing...") -> None:
        """Start the spinner."""
        self._label.set_label(message)
        self._spinner.start()
        self.set_visible(True)

    def stop(self) -> None:
        """Stop the spinner."""
        self._spinner.stop()
        self.set_visible(False)

    def set_message(self, message: str) -> None:
        """Set the status message."""
        self._label.set_label(message)
