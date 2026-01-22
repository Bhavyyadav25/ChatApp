"""Audio level indicator widget."""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from interview_assistant.core.events import Event, get_event_bus


class AudioLevelIndicator(Gtk.Box):
    """
    Visual audio level meter widget.

    Displays real-time audio level from the capture source.
    """

    def __init__(self, width: int = 100, height: int = 8):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        self._level = 0.0
        self._target_level = 0.0
        self._smoothing = 0.3

        # Create the meter
        self._meter_bg = Gtk.Box()
        self._meter_bg.set_size_request(width, height)
        self._meter_bg.add_css_class("audio-meter")

        self._meter_fill = Gtk.Box()
        self._meter_fill.set_size_request(0, height)
        self._meter_fill.add_css_class("audio-meter-fill")
        self._meter_fill.set_halign(Gtk.Align.START)

        # Use an overlay to stack them
        overlay = Gtk.Overlay()
        overlay.set_child(self._meter_bg)
        overlay.add_overlay(self._meter_fill)

        self.append(overlay)

        self._width = width
        self._height = height

        # Subscribe to audio level events
        self._event_bus = get_event_bus()
        self._event_bus.subscribe(Event.AUDIO_LEVEL, self._on_audio_level)

        # Start animation timer
        self._timer_id = GLib.timeout_add(50, self._update_animation)

    def _on_audio_level(self, level: float) -> None:
        """Handle audio level update."""
        self._target_level = min(1.0, max(0.0, level))

    def _update_animation(self) -> bool:
        """Smooth animation update."""
        # Smooth transition
        self._level += (self._target_level - self._level) * self._smoothing

        # Decay
        self._target_level *= 0.95

        # Update meter width
        width = int(self._level * self._width)
        self._meter_fill.set_size_request(width, self._height)

        return True  # Continue timer

    def set_level(self, level: float) -> None:
        """
        Manually set the audio level.

        Args:
            level: Level between 0.0 and 1.0
        """
        self._target_level = min(1.0, max(0.0, level))

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None


class AudioLevelBar(Gtk.DrawingArea):
    """
    Alternative audio level display using custom drawing.

    Provides smoother visuals with gradient.
    """

    def __init__(self, width: int = 120, height: int = 6):
        super().__init__()

        self._level = 0.0
        self._peak = 0.0
        self._peak_hold = 30  # frames

        self.set_size_request(width, height)
        self.set_draw_func(self._draw)

        self._width = width
        self._height = height

        # Subscribe to events
        self._event_bus = get_event_bus()
        self._event_bus.subscribe(Event.AUDIO_LEVEL, self._on_audio_level)

        # Animation timer
        self._timer_id = GLib.timeout_add(33, self._tick)  # ~30fps

    def _on_audio_level(self, level: float) -> None:
        """Handle audio level update."""
        self._level = min(1.0, max(0.0, level))

        # Update peak
        if self._level > self._peak:
            self._peak = self._level
            self._peak_hold = 30

    def _tick(self) -> bool:
        """Animation tick."""
        # Decay peak
        if self._peak_hold > 0:
            self._peak_hold -= 1
        else:
            self._peak *= 0.95

        self.queue_draw()
        return True

    def _draw(self, area, cr, width, height) -> None:
        """Draw the level meter."""
        import cairo

        # Background
        cr.set_source_rgba(0, 0, 0, 0.3)
        self._rounded_rect(cr, 0, 0, width, height, 3)
        cr.fill()

        # Level bar with gradient
        if self._level > 0.01:
            level_width = self._level * width

            # Create gradient
            gradient = cairo.LinearGradient(0, 0, width, 0)
            gradient.add_color_stop_rgba(0, 0.65, 0.89, 0.63, 1)  # Green
            gradient.add_color_stop_rgba(0.6, 0.98, 0.89, 0.69, 1)  # Yellow
            gradient.add_color_stop_rgba(1, 0.95, 0.55, 0.66, 1)  # Red

            cr.set_source(gradient)
            self._rounded_rect(cr, 0, 0, level_width, height, 3)
            cr.fill()

        # Peak marker
        if self._peak > 0.01:
            peak_x = self._peak * width - 2
            cr.set_source_rgba(1, 1, 1, 0.8)
            cr.rectangle(peak_x, 0, 2, height)
            cr.fill()

    def _rounded_rect(self, cr, x, y, width, height, radius) -> None:
        """Draw a rounded rectangle path."""
        import math
        cr.new_path()
        cr.arc(x + radius, y + radius, radius, math.pi, 1.5 * math.pi)
        cr.arc(x + width - radius, y + radius, radius, 1.5 * math.pi, 2 * math.pi)
        cr.arc(x + width - radius, y + height - radius, radius, 0, 0.5 * math.pi)
        cr.arc(x + radius, y + height - radius, radius, 0.5 * math.pi, math.pi)
        cr.close_path()

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
