"""Quick popup mode for stealth operation."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GLib

from typing import Optional, Callable

from interview_assistant.core.config import get_config


class HotkeyPopupMode:
    """
    Quick popup that shows briefly and auto-hides.

    Minimizes the time window is visible during screen share.
    The popup appears on hotkey press and auto-hides after
    a configurable timeout.
    """

    def __init__(
        self,
        parent_window: Optional[Gtk.Window] = None,
        auto_hide_ms: int = 5000,
    ):
        """
        Initialize popup mode.

        Args:
            parent_window: Optional parent window for positioning
            auto_hide_ms: Auto-hide timeout in milliseconds
        """
        self._parent = parent_window
        self._auto_hide_ms = auto_hide_ms
        self._hide_timer: Optional[int] = None

        # Create popup window
        self._popup = Gtk.Window()
        self._popup.set_decorated(False)
        self._popup.set_resizable(False)
        self._popup.set_modal(False)

        # Make it stay on top
        self._popup.set_transient_for(parent_window)

        # Content container
        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._content_box.add_css_class("glass-panel")
        self._content_box.set_margin_top(8)
        self._content_box.set_margin_bottom(8)
        self._content_box.set_margin_start(8)
        self._content_box.set_margin_end(8)

        self._popup.set_child(self._content_box)

        # Default size
        self._popup.set_default_size(400, 300)

        # Callbacks
        self._on_show: Optional[Callable] = None
        self._on_hide: Optional[Callable] = None

    def set_content(self, widget: Gtk.Widget) -> None:
        """
        Set the popup content.

        Args:
            widget: Widget to display in popup
        """
        # Clear existing content
        child = self._content_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self._content_box.remove(child)
            child = next_child

        # Add new content
        self._content_box.append(widget)

    def show(self) -> None:
        """Show the popup."""
        # Cancel any existing hide timer
        if self._hide_timer:
            GLib.source_remove(self._hide_timer)
            self._hide_timer = None

        # Position near cursor or center
        self._position_popup()

        # Show the popup
        self._popup.present()

        # Callback
        if self._on_show:
            self._on_show()

        # Start auto-hide timer
        if self._auto_hide_ms > 0:
            self._hide_timer = GLib.timeout_add(
                self._auto_hide_ms,
                self._auto_hide
            )

    def hide(self) -> None:
        """Hide the popup."""
        if self._hide_timer:
            GLib.source_remove(self._hide_timer)
            self._hide_timer = None

        self._popup.hide()

        if self._on_hide:
            self._on_hide()

    def toggle(self) -> None:
        """Toggle popup visibility."""
        if self._popup.get_visible():
            self.hide()
        else:
            self.show()

    def _auto_hide(self) -> bool:
        """Auto-hide callback."""
        self.hide()
        return False  # Don't repeat

    def _position_popup(self) -> None:
        """Position the popup on screen."""
        # Try to get cursor position
        display = Gdk.Display.get_default()
        if display is None:
            return

        # Get default seat for pointer
        seat = display.get_default_seat()
        if seat:
            pointer = seat.get_pointer()
            if pointer:
                # Note: GTK4 doesn't have easy cursor position API
                # Position will be determined by window manager
                pass

    def extend_timeout(self, additional_ms: int = 3000) -> None:
        """
        Extend the auto-hide timeout.

        Useful when user is actively viewing content.

        Args:
            additional_ms: Additional time to add
        """
        if self._hide_timer:
            GLib.source_remove(self._hide_timer)

        self._hide_timer = GLib.timeout_add(
            additional_ms,
            self._auto_hide
        )

    def set_auto_hide_timeout(self, ms: int) -> None:
        """Set the auto-hide timeout."""
        self._auto_hide_ms = ms

    def set_on_show(self, callback: Callable) -> None:
        """Set callback for when popup is shown."""
        self._on_show = callback

    def set_on_hide(self, callback: Callable) -> None:
        """Set callback for when popup is hidden."""
        self._on_hide = callback

    @property
    def is_visible(self) -> bool:
        """Check if popup is currently visible."""
        return self._popup.get_visible()

    @property
    def window(self) -> Gtk.Window:
        """Get the underlying popup window."""
        return self._popup


class AnswerPopup(HotkeyPopupMode):
    """
    Specialized popup for displaying AI answers.

    Shows the current answer in a compact popup format.
    """

    def __init__(self, parent_window: Optional[Gtk.Window] = None):
        config = get_config()
        super().__init__(
            parent_window=parent_window,
            auto_hide_ms=config.stealth.auto_hide_timeout,
        )

        # Build answer display
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the popup UI."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        title = Gtk.Label(label="Answer")
        title.add_css_class("heading")
        header.append(title)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header.append(spacer)

        # Close button
        close_btn = Gtk.Button()
        close_btn.set_icon_name("window-close-symbolic")
        close_btn.add_css_class("flat")
        close_btn.connect("clicked", lambda _: self.hide())
        header.append(close_btn)

        main_box.append(header)

        # Answer text
        self._text_view = Gtk.TextView()
        self._text_view.set_editable(False)
        self._text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._text_view.add_css_class("answer-text")

        self._buffer = self._text_view.get_buffer()

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self._text_view)
        scroll.set_vexpand(True)
        scroll.set_min_content_height(200)

        main_box.append(scroll)

        # Pin button (disable auto-hide)
        pin_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self._pin_button = Gtk.ToggleButton(label="Pin")
        self._pin_button.add_css_class("flat")
        self._pin_button.connect("toggled", self._on_pin_toggled)
        pin_box.append(self._pin_button)

        main_box.append(pin_box)

        self.set_content(main_box)

    def _on_pin_toggled(self, button) -> None:
        """Handle pin button toggle."""
        if button.get_active():
            # Disable auto-hide
            if self._hide_timer:
                GLib.source_remove(self._hide_timer)
                self._hide_timer = None
        else:
            # Re-enable auto-hide
            if self.is_visible:
                self._hide_timer = GLib.timeout_add(
                    self._auto_hide_ms,
                    self._auto_hide
                )

    def set_answer(self, text: str) -> None:
        """Set the answer text."""
        self._buffer.set_text(text)

    def append_answer(self, text: str) -> None:
        """Append to the answer text."""
        end_iter = self._buffer.get_end_iter()
        self._buffer.insert(end_iter, text)

    def clear(self) -> None:
        """Clear the answer."""
        self._buffer.set_text("")
