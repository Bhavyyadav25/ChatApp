"""Multi-monitor display management for stealth modes."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MonitorInfo:
    """Information about a monitor."""
    index: int
    name: str
    is_primary: bool
    x: int
    y: int
    width: int
    height: int
    scale_factor: float
    refresh_rate: float

    @property
    def geometry(self) -> Gdk.Rectangle:
        """Get monitor geometry as Gdk.Rectangle."""
        rect = Gdk.Rectangle()
        rect.x = self.x
        rect.y = self.y
        rect.width = self.width
        rect.height = self.height
        return rect


class DisplayManager:
    """
    Manages window placement across multiple monitors.

    Enables 'secondary monitor only' mode where the window
    is placed on a non-shared monitor.
    """

    def __init__(self):
        self._display = Gdk.Display.get_default()
        self._monitors: List[MonitorInfo] = []
        self._refresh_monitors()

    def _refresh_monitors(self) -> None:
        """Refresh the list of available monitors."""
        self._monitors = []

        if self._display is None:
            return

        monitors = self._display.get_monitors()
        primary = None

        # Try to get primary monitor
        # Note: GTK4 removed get_primary_monitor, so we detect by position
        for i in range(monitors.get_n_items()):
            monitor = monitors.get_item(i)
            geo = monitor.get_geometry()
            if geo.x == 0 and geo.y == 0:
                primary = monitor
                break

        for i in range(monitors.get_n_items()):
            monitor = monitors.get_item(i)
            geo = monitor.get_geometry()

            info = MonitorInfo(
                index=i,
                name=monitor.get_model() or f"Monitor {i}",
                is_primary=(monitor == primary) if primary else (i == 0),
                x=geo.x,
                y=geo.y,
                width=geo.width,
                height=geo.height,
                scale_factor=monitor.get_scale_factor(),
                refresh_rate=monitor.get_refresh_rate() / 1000.0,  # Convert to Hz
            )
            self._monitors.append(info)

    def get_monitors(self) -> List[MonitorInfo]:
        """Get list of all monitors."""
        return self._monitors.copy()

    def get_primary_monitor(self) -> Optional[MonitorInfo]:
        """Get the primary monitor."""
        for m in self._monitors:
            if m.is_primary:
                return m
        return self._monitors[0] if self._monitors else None

    def get_secondary_monitors(self) -> List[MonitorInfo]:
        """Get all non-primary monitors."""
        return [m for m in self._monitors if not m.is_primary]

    def get_monitor_at_window(self, window: Gtk.Window) -> Optional[MonitorInfo]:
        """
        Get the monitor that contains a window.

        Args:
            window: GTK window

        Returns:
            MonitorInfo for the containing monitor
        """
        surface = window.get_surface()
        if surface is None:
            return None

        # Get the monitor for this surface
        display = window.get_display()
        if display is None:
            return self.get_primary_monitor()

        monitor = display.get_monitor_at_surface(surface)
        if monitor is None:
            return self.get_primary_monitor()

        # Find matching MonitorInfo
        geo = monitor.get_geometry()
        for m in self._monitors:
            if m.x == geo.x and m.y == geo.y:
                return m

        return self.get_primary_monitor()

    def move_to_monitor(self, window: Gtk.Window, monitor: MonitorInfo) -> bool:
        """
        Move a window to a specific monitor.

        Note: GTK4 has limited control over window positioning.
        This uses fullscreen on monitor as a workaround.

        Args:
            window: GTK window to move
            monitor: Target monitor

        Returns:
            True if move was attempted
        """
        try:
            # Get the Gdk monitor
            if self._display is None:
                return False

            monitors = self._display.get_monitors()
            if monitor.index >= monitors.get_n_items():
                return False

            gdk_monitor = monitors.get_item(monitor.index)

            # Fullscreen on the target monitor
            window.fullscreen_on_monitor(gdk_monitor)

            # Then unfullscreen to get normal window
            # window.unfullscreen()

            return True

        except Exception as e:
            print(f"Error moving window to monitor: {e}")
            return False

    def move_to_secondary(self, window: Gtk.Window) -> bool:
        """
        Move window to a secondary (non-primary) monitor.

        This is the most reliable stealth mode as most users
        share only their primary monitor.

        Args:
            window: GTK window to move

        Returns:
            True if moved successfully
        """
        secondary = self.get_secondary_monitors()
        if not secondary:
            print("No secondary monitor available")
            return False

        return self.move_to_monitor(window, secondary[0])

    def has_multiple_monitors(self) -> bool:
        """Check if system has multiple monitors."""
        return len(self._monitors) > 1

    def refresh(self) -> None:
        """Refresh monitor information."""
        self._refresh_monitors()


class MonitorAwareWindow:
    """
    Mixin for windows that need monitor awareness.

    Provides utilities for monitor-based positioning.
    """

    def __init__(self, window: Gtk.Window):
        self.window = window
        self.display_manager = DisplayManager()
        self._target_monitor: Optional[MonitorInfo] = None

    def set_target_monitor(self, monitor: Optional[MonitorInfo]) -> None:
        """Set the target monitor for this window."""
        self._target_monitor = monitor

    def move_to_target(self) -> bool:
        """Move window to target monitor."""
        if self._target_monitor:
            return self.display_manager.move_to_monitor(
                self.window, self._target_monitor
            )
        return False

    def move_to_secondary(self) -> bool:
        """Move window to secondary monitor."""
        return self.display_manager.move_to_secondary(self.window)

    def stay_on_current_monitor(self) -> None:
        """Try to keep window on its current monitor."""
        current = self.display_manager.get_monitor_at_window(self.window)
        if current:
            self._target_monitor = current

    def get_current_monitor(self) -> Optional[MonitorInfo]:
        """Get the monitor the window is currently on."""
        return self.display_manager.get_monitor_at_window(self.window)
