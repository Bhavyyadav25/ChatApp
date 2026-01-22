"""Main GTK4 Application for Interview Assistant."""

import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")

from gi.repository import Gtk, Adw, Gio, GLib

from interview_assistant import __app_id__, __app_name__, __version__
from interview_assistant.core.config import get_config, CONFIG_DIR
from interview_assistant.core.events import get_event_bus


class InterviewAssistantApp(Adw.Application):
    """
    Main Interview Assistant application.

    Manages the application lifecycle, windows, and global actions.
    """

    def __init__(self):
        super().__init__(
            application_id=__app_id__,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

        self.main_window = None
        self._config = get_config()
        self._event_bus = get_event_bus()

        # Connect signals
        self.connect("activate", self.on_activate)
        self.connect("shutdown", self.on_shutdown)

        # Set up actions
        self._setup_actions()

    def _setup_actions(self) -> None:
        """Set up application actions."""
        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit)
        self.add_action(quit_action)

        # Settings action
        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self._on_settings)
        self.add_action(settings_action)

        # History action
        history_action = Gio.SimpleAction.new("history", None)
        history_action.connect("activate", self._on_history)
        self.add_action(history_action)

        # About action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        # Set up keyboard shortcuts
        self.set_accels_for_action("app.quit", ["<Control>q"])

    def on_activate(self, app) -> None:
        """Handle application activation."""
        if not self.main_window:
            # Ensure config directory exists
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)

            # Start web viewer for phone access
            from interview_assistant.services.web_viewer import get_web_viewer
            self._web_viewer = get_web_viewer()
            self._web_viewer.start()

            # Create main window
            from interview_assistant.ui.main_window import MainWindow
            self.main_window = MainWindow(self)

        self.main_window.present()

    def on_shutdown(self, app) -> None:
        """Handle application shutdown."""
        # Clean up resources
        if self.main_window:
            self.main_window.cleanup()

        # Disable events
        self._event_bus.disable()

        # Save configuration
        try:
            self._config.save()
        except Exception as e:
            print(f"Error saving config: {e}")

    def _on_quit(self, action, param) -> None:
        """Handle quit action."""
        self.quit()

    def _on_settings(self, action, param) -> None:
        """Handle settings action."""
        from interview_assistant.ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.main_window)
        dialog.present()

    def _on_history(self, action, param) -> None:
        """Handle history action."""
        from interview_assistant.ui.history_view import HistoryDialog
        dialog = HistoryDialog(self.main_window)
        dialog.present()

    def _on_about(self, action, param) -> None:
        """Handle about action."""
        about = Adw.AboutWindow(
            transient_for=self.main_window,
            application_name=__app_name__,
            application_icon=__app_id__,
            version=__version__,
            developer_name="Interview Assistant",
            developers=["Interview Assistant Team"],
            copyright="2024 Interview Assistant",
            license_type=Gtk.License.MIT_X11,
            website="https://github.com/interview-assistant/interview-assistant",
            issue_url="https://github.com/interview-assistant/interview-assistant/issues",
            comments="AI-powered interview assistant for Linux with screen-share avoidance",
        )
        about.present()


def main():
    """Main entry point."""
    app = InterviewAssistantApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
