"""X11 window property manipulation for screen-share avoidance."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GLib

from typing import Optional


class X11StealthWindow:
    """
    X11-specific techniques for screen-share avoidance.

    NOTE: These techniques are not guaranteed to work with all
    screen capture tools. Effectiveness varies based on:
    - How the capture tool reads the screen (X11 vs XComposite vs portal)
    - Desktop environment and compositor
    - Screen sharing method (entire screen vs window)

    Available modes:
    - 'dock': Set window type to DOCK (like a panel)
    - 'popup': Set window type to POPUP_MENU
    - 'tooltip': Set window type to TOOLTIP
    - 'override': Use override_redirect (no WM decorations)
    """

    # Window type atoms
    WINDOW_TYPES = {
        'dock': '_NET_WM_WINDOW_TYPE_DOCK',
        'popup': '_NET_WM_WINDOW_TYPE_POPUP_MENU',
        'tooltip': '_NET_WM_WINDOW_TYPE_TOOLTIP',
        'notification': '_NET_WM_WINDOW_TYPE_NOTIFICATION',
        'dropdown': '_NET_WM_WINDOW_TYPE_DROPDOWN_MENU',
        'utility': '_NET_WM_WINDOW_TYPE_UTILITY',
    }

    def __init__(self, gtk_window: Gtk.Window):
        """
        Initialize X11 stealth window.

        Args:
            gtk_window: GTK4 window to apply stealth to
        """
        self.window = gtk_window
        self._display = None
        self._x_window = None
        self._original_type = None

        # Try to import Xlib
        try:
            from Xlib import display as xdisplay
            from Xlib import X, Xatom
            self._xlib_available = True
            self._X = X
            self._Xatom = Xatom
        except ImportError:
            self._xlib_available = False
            print("python-xlib not available. X11 stealth features disabled.")

    def _get_x11_window(self):
        """Get the X11 window ID from the GTK surface."""
        if not self._xlib_available:
            return None

        try:
            from Xlib import display as xdisplay

            surface = self.window.get_surface()
            if surface is None:
                return None

            # GTK4 on X11 should have get_xid()
            if hasattr(surface, 'get_xid'):
                xid = surface.get_xid()

                if self._display is None:
                    self._display = xdisplay.Display()

                self._x_window = self._display.create_resource_object('window', xid)
                return self._x_window

        except Exception as e:
            print(f"Error getting X11 window: {e}")

        return None

    def apply_stealth_mode(self, mode: str) -> bool:
        """
        Apply stealth properties to the window.

        Args:
            mode: Stealth mode ('dock', 'popup', 'tooltip', etc.)

        Returns:
            True if applied successfully
        """
        if not self._xlib_available:
            return False

        x_window = self._get_x11_window()
        if x_window is None:
            return False

        try:
            window_type = self.WINDOW_TYPES.get(mode)
            if not window_type:
                return False

            # Get atoms
            type_atom = self._display.intern_atom('_NET_WM_WINDOW_TYPE')
            window_type_atom = self._display.intern_atom(window_type)

            # Store original type
            if self._original_type is None:
                try:
                    self._original_type = x_window.get_full_property(
                        type_atom, self._Xatom.ATOM
                    )
                except Exception:
                    pass

            # Set new window type
            x_window.change_property(
                type_atom,
                self._Xatom.ATOM,
                32,
                [window_type_atom]
            )

            self._display.sync()
            return True

        except Exception as e:
            print(f"Error applying stealth mode: {e}")
            return False

    def set_skip_taskbar(self, skip: bool = True) -> bool:
        """
        Set the window to skip taskbar and pager.

        This can help hide the window from some capture tools.

        Args:
            skip: Whether to skip taskbar/pager

        Returns:
            True if applied successfully
        """
        if not self._xlib_available:
            return False

        x_window = self._get_x11_window()
        if x_window is None:
            return False

        try:
            state_atom = self._display.intern_atom('_NET_WM_STATE')
            skip_taskbar = self._display.intern_atom('_NET_WM_STATE_SKIP_TASKBAR')
            skip_pager = self._display.intern_atom('_NET_WM_STATE_SKIP_PAGER')

            states = [skip_taskbar, skip_pager] if skip else []

            x_window.change_property(
                state_atom,
                self._Xatom.ATOM,
                32,
                states
            )

            self._display.sync()
            return True

        except Exception as e:
            print(f"Error setting skip taskbar: {e}")
            return False

    def set_always_on_top(self, on_top: bool = True) -> bool:
        """
        Set the window to always stay on top.

        Args:
            on_top: Whether to stay on top

        Returns:
            True if applied successfully
        """
        if not self._xlib_available:
            return False

        x_window = self._get_x11_window()
        if x_window is None:
            return False

        try:
            state_atom = self._display.intern_atom('_NET_WM_STATE')
            above_atom = self._display.intern_atom('_NET_WM_STATE_ABOVE')

            # Get current states
            current = x_window.get_full_property(state_atom, self._Xatom.ATOM)
            states = list(current.value) if current else []

            if on_top:
                if above_atom not in states:
                    states.append(above_atom)
            else:
                if above_atom in states:
                    states.remove(above_atom)

            x_window.change_property(
                state_atom,
                self._Xatom.ATOM,
                32,
                states
            )

            self._display.sync()
            return True

        except Exception as e:
            print(f"Error setting always on top: {e}")
            return False

    def set_compositor_bypass(self, bypass: bool = True) -> bool:
        """
        Set compositor bypass hint.

        This is primarily for performance but may affect capture.

        Args:
            bypass: Whether to bypass compositor

        Returns:
            True if applied successfully
        """
        if not self._xlib_available:
            return False

        x_window = self._get_x11_window()
        if x_window is None:
            return False

        try:
            bypass_atom = self._display.intern_atom('_NET_WM_BYPASS_COMPOSITOR')

            x_window.change_property(
                bypass_atom,
                self._Xatom.CARDINAL,
                32,
                [1 if bypass else 0]
            )

            self._display.sync()
            return True

        except Exception as e:
            print(f"Error setting compositor bypass: {e}")
            return False

    def restore_normal(self) -> bool:
        """
        Restore the window to normal state.

        Returns:
            True if restored successfully
        """
        if not self._xlib_available:
            return False

        x_window = self._get_x11_window()
        if x_window is None:
            return False

        try:
            # Restore original window type
            if self._original_type:
                type_atom = self._display.intern_atom('_NET_WM_WINDOW_TYPE')
                x_window.change_property(
                    type_atom,
                    self._Xatom.ATOM,
                    32,
                    list(self._original_type.value)
                )

            # Remove skip taskbar/pager
            self.set_skip_taskbar(False)

            # Remove always on top
            self.set_always_on_top(False)

            # Remove compositor bypass
            self.set_compositor_bypass(False)

            self._display.sync()
            return True

        except Exception as e:
            print(f"Error restoring window: {e}")
            return False

    @property
    def is_available(self) -> bool:
        """Check if X11 stealth features are available."""
        return self._xlib_available


def is_x11_session() -> bool:
    """Check if running under X11."""
    display = Gdk.Display.get_default()
    if display is None:
        return False

    # Check display type
    display_name = type(display).__name__
    return 'X11' in display_name


def is_wayland_session() -> bool:
    """Check if running under Wayland."""
    display = Gdk.Display.get_default()
    if display is None:
        return False

    display_name = type(display).__name__
    return 'Wayland' in display_name
