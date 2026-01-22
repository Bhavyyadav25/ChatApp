"""System tray integration."""

import threading
from typing import Callable, Optional

from interview_assistant.core.events import Event, get_event_bus


class SystemTray:
    """
    System tray icon for Interview Assistant.

    Provides quick access to:
    - Toggle recording
    - Toggle window visibility
    - Change interview mode
    - Quit application
    """

    def __init__(
        self,
        on_toggle_window: Optional[Callable] = None,
        on_toggle_recording: Optional[Callable] = None,
        on_quit: Optional[Callable] = None,
    ):
        """
        Initialize system tray.

        Args:
            on_toggle_window: Callback to toggle main window
            on_toggle_recording: Callback to toggle recording
            on_quit: Callback to quit application
        """
        self._on_toggle_window = on_toggle_window
        self._on_toggle_recording = on_toggle_recording
        self._on_quit = on_quit

        self._icon = None
        self._is_recording = False
        self._event_bus = get_event_bus()

        # Subscribe to events
        self._event_bus.subscribe(Event.RECORDING_STARTED, lambda _: self._set_recording(True))
        self._event_bus.subscribe(Event.RECORDING_STOPPED, lambda _: self._set_recording(False))

    def start(self) -> bool:
        """
        Start the system tray icon.

        Returns:
            True if started successfully
        """
        try:
            import pystray
            from PIL import Image

            # Create icon image
            icon_image = self._create_icon()

            # Create menu
            menu = pystray.Menu(
                pystray.MenuItem(
                    "Show/Hide Window",
                    self._on_show_window,
                    default=True,
                ),
                pystray.MenuItem(
                    lambda item: "Stop Recording" if self._is_recording else "Start Recording",
                    self._on_record_toggle,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("DSA Mode", self._on_dsa_mode),
                pystray.MenuItem("System Design Mode", self._on_system_design_mode),
                pystray.MenuItem("Behavioral Mode", self._on_behavioral_mode),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._on_quit_click),
            )

            # Create icon
            self._icon = pystray.Icon(
                "interview-assistant",
                icon_image,
                "Interview Assistant",
                menu,
            )

            # Run in background thread
            thread = threading.Thread(target=self._icon.run, daemon=True)
            thread.start()

            return True

        except ImportError:
            print("pystray not installed. System tray disabled.")
            return False
        except Exception as e:
            print(f"Error starting system tray: {e}")
            return False

    def stop(self) -> None:
        """Stop the system tray icon."""
        if self._icon:
            self._icon.stop()
            self._icon = None

    def _create_icon(self):
        """Create the tray icon image."""
        from PIL import Image, ImageDraw

        # Create a simple icon
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Draw a circle with gradient-like effect
        center = size // 2
        radius = size // 2 - 4

        # Background circle
        draw.ellipse(
            [4, 4, size - 4, size - 4],
            fill=(89, 180, 250, 255),
        )

        # Inner circle
        inner_radius = radius - 8
        draw.ellipse(
            [center - inner_radius, center - inner_radius,
             center + inner_radius, center + inner_radius],
            fill=(30, 30, 46, 255),
        )

        # Recording indicator (small dot)
        if self._is_recording:
            dot_radius = 8
            draw.ellipse(
                [size - dot_radius * 2 - 2, 2,
                 size - 2, dot_radius * 2 + 2],
                fill=(243, 139, 168, 255),
            )

        return image

    def _set_recording(self, is_recording: bool) -> None:
        """Update recording state."""
        self._is_recording = is_recording

        # Update icon if possible
        if self._icon:
            try:
                self._icon.icon = self._create_icon()
            except Exception:
                pass

    def _on_show_window(self, icon, item) -> None:
        """Handle show window menu item."""
        if self._on_toggle_window:
            self._on_toggle_window()

    def _on_record_toggle(self, icon, item) -> None:
        """Handle recording toggle."""
        if self._on_toggle_recording:
            self._on_toggle_recording()

    def _on_dsa_mode(self, icon, item) -> None:
        """Switch to DSA mode."""
        from interview_assistant.ai.prompts import InterviewType
        self._event_bus.emit(Event.INTERVIEW_TYPE_CHANGED, InterviewType.DSA)

    def _on_system_design_mode(self, icon, item) -> None:
        """Switch to System Design mode."""
        from interview_assistant.ai.prompts import InterviewType
        self._event_bus.emit(Event.INTERVIEW_TYPE_CHANGED, InterviewType.SYSTEM_DESIGN)

    def _on_behavioral_mode(self, icon, item) -> None:
        """Switch to Behavioral mode."""
        from interview_assistant.ai.prompts import InterviewType
        self._event_bus.emit(Event.INTERVIEW_TYPE_CHANGED, InterviewType.BEHAVIORAL)

    def _on_quit_click(self, icon, item) -> None:
        """Handle quit menu item."""
        self.stop()
        if self._on_quit:
            self._on_quit()

    def show_notification(self, title: str, message: str) -> None:
        """
        Show a notification from the tray.

        Args:
            title: Notification title
            message: Notification message
        """
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception as e:
                print(f"Error showing notification: {e}")

    @property
    def is_running(self) -> bool:
        """Check if tray is running."""
        return self._icon is not None
