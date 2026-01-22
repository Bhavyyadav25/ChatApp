"""Screen-share resistant overlay window."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GLib

from typing import Optional

from interview_assistant.core.config import get_config, StealthMode
from interview_assistant.core.events import Event, get_event_bus
from interview_assistant.stealth.x11_bypass import X11StealthWindow, is_x11_session
from interview_assistant.stealth.display_manager import DisplayManager
from interview_assistant.stealth.hotkey_popup import AnswerPopup

from .answer_view import AnswerView
from .transcript_view import TranscriptView


class OverlayWindow(Gtk.Window):
    """
    Screen-share resistant overlay window.

    Implements multiple stealth techniques:
    - X11 window type manipulation
    - Secondary monitor placement
    - Auto-hiding popup mode
    """

    def __init__(self, app):
        super().__init__()

        self._app = app
        self._config = get_config()
        self._event_bus = get_event_bus()

        # Stealth components
        self._x11_stealth: Optional[X11StealthWindow] = None
        self._display_manager = DisplayManager()
        self._popup_mode: Optional[AnswerPopup] = None

        # Current stealth mode
        self._stealth_mode = self._config.stealth.mode

        self._setup_window()
        self._build_ui()
        self._apply_stealth_mode()
        self._connect_events()

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.set_title("Interview Assistant - Overlay")
        self.set_decorated(False)
        self.set_resizable(True)

        # Set size from config
        self.set_default_size(600, 400)

        # Make window transparent
        self.add_css_class("overlay-mode")

        # Set opacity
        # Note: GTK4 uses CSS for opacity
        opacity = self._config.stealth.opacity
        css = f"window {{ opacity: {opacity}; }}"
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
        )

    def _build_ui(self) -> None:
        """Build the overlay UI."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.add_css_class("glass-panel")
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)
        main_box.set_margin_start(8)
        main_box.set_margin_end(8)

        # Minimal header with drag area
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        # Title (also acts as drag handle)
        title = Gtk.Label(label="Answer")
        title.add_css_class("heading")
        header.append(title)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header.append(spacer)

        # Stealth mode indicator
        self._mode_label = Gtk.Label()
        self._mode_label.add_css_class("text-muted")
        header.append(self._mode_label)

        # Close button
        close_btn = Gtk.Button()
        close_btn.set_icon_name("window-close-symbolic")
        close_btn.add_css_class("flat")
        close_btn.connect("clicked", lambda _: self.hide())
        header.append(close_btn)

        main_box.append(header)

        # Answer view
        self._answer_view = AnswerView()
        self._answer_view.set_vexpand(True)
        main_box.append(self._answer_view)

        self.set_child(main_box)

        # Make window draggable
        gesture = Gtk.GestureDrag()
        gesture.connect("drag-begin", self._on_drag_begin)
        gesture.connect("drag-update", self._on_drag_update)
        header.add_controller(gesture)

    def _on_drag_begin(self, gesture, x, y) -> None:
        """Handle drag start."""
        self._drag_start_x = x
        self._drag_start_y = y

    def _on_drag_update(self, gesture, offset_x, offset_y) -> None:
        """Handle drag update."""
        # Note: GTK4 has limited window moving API
        # This is a simplified implementation
        pass

    def _apply_stealth_mode(self) -> None:
        """Apply the current stealth mode."""
        mode = self._stealth_mode

        # Update mode label
        mode_names = {
            StealthMode.NORMAL: "Normal",
            StealthMode.OVERLAY: "Overlay",
            StealthMode.SECONDARY_MONITOR: "Secondary Monitor",
            StealthMode.HOTKEY_POPUP: "Popup",
        }
        self._mode_label.set_label(mode_names.get(mode, "Unknown"))

        if mode == StealthMode.OVERLAY:
            self._apply_overlay_mode()
        elif mode == StealthMode.SECONDARY_MONITOR:
            self._apply_secondary_monitor_mode()
        elif mode == StealthMode.HOTKEY_POPUP:
            self._apply_popup_mode()
        else:
            self._apply_normal_mode()

    def _apply_normal_mode(self) -> None:
        """Apply normal window mode (no stealth)."""
        if self._x11_stealth:
            self._x11_stealth.restore_normal()

    def _apply_overlay_mode(self) -> None:
        """Apply X11 overlay mode."""
        if is_x11_session():
            if not self._x11_stealth:
                self._x11_stealth = X11StealthWindow(self)

            # Try different window types
            # 'popup' or 'dock' often work best
            self._x11_stealth.apply_stealth_mode('popup')
            self._x11_stealth.set_skip_taskbar(True)

            if self._config.stealth.always_on_top:
                self._x11_stealth.set_always_on_top(True)

    def _apply_secondary_monitor_mode(self) -> None:
        """Apply secondary monitor mode."""
        if self._display_manager.has_multiple_monitors():
            self._display_manager.move_to_secondary(self)
        else:
            print("No secondary monitor available, using normal mode")
            self._apply_normal_mode()

    def _apply_popup_mode(self) -> None:
        """Apply popup mode (auto-hiding)."""
        if not self._popup_mode:
            self._popup_mode = AnswerPopup()

        # Hide main overlay, use popup instead
        self.hide()

    def _connect_events(self) -> None:
        """Connect to events."""
        self._event_bus.subscribe(Event.STEALTH_MODE_CHANGED, self._on_mode_changed)
        self._event_bus.subscribe(Event.AI_RESPONSE_COMPLETE, self._on_answer_complete)

    def _on_mode_changed(self, mode: StealthMode) -> None:
        """Handle stealth mode change."""
        self._stealth_mode = mode
        self._apply_stealth_mode()

    def _on_answer_complete(self, response) -> None:
        """Handle AI answer completion."""
        if self._stealth_mode == StealthMode.HOTKEY_POPUP and self._popup_mode:
            self._popup_mode.set_answer(response if isinstance(response, str) else str(response))
            self._popup_mode.show()

    def set_stealth_mode(self, mode: StealthMode) -> None:
        """
        Set the stealth mode.

        Args:
            mode: New stealth mode
        """
        self._stealth_mode = mode
        self._apply_stealth_mode()
        self._event_bus.emit(Event.STEALTH_MODE_CHANGED, mode)

    def show_answer(self, text: str) -> None:
        """
        Show an answer in the overlay.

        Args:
            text: Answer text to display
        """
        if self._stealth_mode == StealthMode.HOTKEY_POPUP:
            if self._popup_mode:
                self._popup_mode.set_answer(text)
                self._popup_mode.show()
        else:
            self._answer_view.set_text(text)
            self.present()

    def toggle_visibility(self) -> None:
        """Toggle overlay visibility."""
        if self._stealth_mode == StealthMode.HOTKEY_POPUP:
            if self._popup_mode:
                self._popup_mode.toggle()
        else:
            if self.get_visible():
                self.hide()
            else:
                self.present()

    @property
    def stealth_mode(self) -> StealthMode:
        """Get current stealth mode."""
        return self._stealth_mode
