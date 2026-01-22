"""Interview mode selector widget."""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject

from interview_assistant.ai.prompts import InterviewType, get_all_interview_types
from interview_assistant.core.events import Event, get_event_bus


class ModeSelector(Gtk.Box):
    """
    Interview mode selector dropdown.

    Allows switching between DSA, System Design, and Behavioral modes.
    """

    __gsignals__ = {
        'mode-changed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._current_mode = InterviewType.DSA
        self._event_bus = get_event_bus()

        # Label
        label = Gtk.Label(label="Mode:")
        label.add_css_class("text-muted")
        self.append(label)

        # Create dropdown
        self._dropdown = Gtk.DropDown()

        # Create string list model
        self._model = Gtk.StringList()
        self._modes = []

        for mode, display_name in get_all_interview_types():
            self._model.append(display_name)
            self._modes.append(mode)

        self._dropdown.set_model(self._model)
        self._dropdown.connect("notify::selected", self._on_selection_changed)

        self.append(self._dropdown)

    def _on_selection_changed(self, dropdown, _) -> None:
        """Handle dropdown selection change."""
        index = dropdown.get_selected()
        if 0 <= index < len(self._modes):
            self._current_mode = self._modes[index]
            self.emit('mode-changed', self._current_mode.value)
            self._event_bus.emit(Event.INTERVIEW_TYPE_CHANGED, self._current_mode)

    def get_mode(self) -> InterviewType:
        """Get the currently selected mode."""
        return self._current_mode

    def set_mode(self, mode: InterviewType) -> None:
        """
        Set the current mode.

        Args:
            mode: Interview type to select
        """
        try:
            index = self._modes.index(mode)
            self._dropdown.set_selected(index)
            self._current_mode = mode
        except ValueError:
            pass


class ModeSelectorButtons(Gtk.Box):
    """
    Alternative mode selector using toggle buttons.

    More visual feedback than dropdown.
    """

    __gsignals__ = {
        'mode-changed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        self._current_mode = InterviewType.DSA
        self._buttons = {}
        self._event_bus = get_event_bus()

        # Create toggle buttons for each mode
        first_button = None

        for mode, display_name in get_all_interview_types():
            button = Gtk.ToggleButton(label=display_name)
            button.add_css_class("toggle-button")

            # Add mode-specific badge class
            badge_class = mode.value.replace("_", "-")
            button.add_css_class(f"badge-{badge_class}")

            # Make them act as radio buttons
            if first_button:
                button.set_group(first_button)
            else:
                first_button = button
                button.set_active(True)

            button.connect("toggled", self._on_button_toggled, mode)
            self._buttons[mode] = button
            self.append(button)

    def _on_button_toggled(self, button, mode: InterviewType) -> None:
        """Handle button toggle."""
        if button.get_active():
            self._current_mode = mode
            self.emit('mode-changed', mode.value)
            self._event_bus.emit(Event.INTERVIEW_TYPE_CHANGED, mode)

    def get_mode(self) -> InterviewType:
        """Get the currently selected mode."""
        return self._current_mode

    def set_mode(self, mode: InterviewType) -> None:
        """Set the current mode."""
        if mode in self._buttons:
            self._buttons[mode].set_active(True)
            self._current_mode = mode


class InterviewTypeBadge(Gtk.Label):
    """
    Badge showing current interview type.
    """

    def __init__(self, interview_type: InterviewType = InterviewType.DSA):
        super().__init__()

        self._type = interview_type
        self.add_css_class("badge")
        self._update_badge()

        # Subscribe to mode changes
        self._event_bus = get_event_bus()
        self._event_bus.subscribe(Event.INTERVIEW_TYPE_CHANGED, self._on_mode_changed)

    def _on_mode_changed(self, mode: InterviewType) -> None:
        """Handle mode change."""
        self._type = mode
        self._update_badge()

    def _update_badge(self) -> None:
        """Update badge appearance."""
        # Remove old classes
        for cls in ["dsa", "system-design", "behavioral"]:
            self.remove_css_class(cls)

        # Set text and class
        display_names = {
            InterviewType.DSA: ("DSA", "dsa"),
            InterviewType.SYSTEM_DESIGN: ("System Design", "system-design"),
            InterviewType.BEHAVIORAL: ("Behavioral", "behavioral"),
        }

        name, css_class = display_names.get(self._type, ("Unknown", ""))
        self.set_label(name)
        if css_class:
            self.add_css_class(css_class)

    def set_type(self, interview_type: InterviewType) -> None:
        """Set the interview type."""
        self._type = interview_type
        self._update_badge()
