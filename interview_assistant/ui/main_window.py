"""Main application window."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GLib, Gio

from pathlib import Path
import asyncio
import threading

from interview_assistant.core.config import get_config
from interview_assistant.core.events import Event, get_event_bus
from interview_assistant.core.session import SessionManager, InterviewType
from interview_assistant.audio.capture import SystemAudioCapture
from interview_assistant.transcription.streaming import StreamingTranscriber, StreamingConfig
from interview_assistant.ai.assistant import AIAssistant, get_ai_assistant
from interview_assistant.ai.prompts import InterviewType as AIInterviewType

from .transcript_view import TranscriptView
from .answer_view import AnswerView
from .widgets.audio_level import AudioLevelBar
from .widgets.status_indicator import StatusIndicator, RecordButton
from .widgets.mode_selector import ModeSelector

from interview_assistant.stealth.x11_bypass import X11StealthWindow, is_x11_session
from interview_assistant.core.config import StealthMode


class MainWindow(Adw.ApplicationWindow):
    """
    Main application window with glassmorphism theme.
    """

    def __init__(self, app):
        super().__init__(application=app)

        self._app = app
        self._config = get_config()
        self._event_bus = get_event_bus()

        # Initialize components
        self._session_manager = SessionManager()
        self._audio_capture = None
        self._transcriber = None
        self._ai_assistant = None

        # Async event loop for AI calls
        self._loop = None
        self._loop_thread = None

        # Stealth mode
        self._stealth_window = None

        # Set up window
        self._setup_window()
        self._load_styles()
        self._build_ui()
        self._connect_events()
        self._start_async_loop()

        # Apply stealth mode after window is shown
        self.connect("realize", self._on_window_realize)

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.set_title("Interview Assistant")
        self.set_default_size(
            self._config.ui.window_width,
            self._config.ui.window_height
        )

        # Set minimum size
        self.set_size_request(600, 400)

    def _load_styles(self) -> None:
        """Load CSS styles."""
        css_provider = Gtk.CssProvider()

        # Try to load from package resources
        css_paths = [
            Path(__file__).parent.parent / "resources" / "styles" / "glassmorphism.css",
            Path.home() / ".config" / "interview-assistant" / "styles" / "custom.css",
        ]

        for css_path in css_paths:
            if css_path.exists():
                try:
                    css_provider.load_from_path(str(css_path))
                    Gtk.StyleContext.add_provider_for_display(
                        Gdk.Display.get_default(),
                        css_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                    )
                except Exception as e:
                    print(f"Error loading CSS from {css_path}: {e}")

    def _build_ui(self) -> None:
        """Build the main UI layout."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Header bar
        header = self._build_header()
        main_box.append(header)

        # Content area
        content = self._build_content()
        main_box.append(content)

        # Status bar
        status_bar = self._build_status_bar()
        main_box.append(status_bar)

        self.set_content(main_box)

    def _build_header(self) -> Adw.HeaderBar:
        """Build the header bar."""
        header = Adw.HeaderBar()

        # Left side: Record button and mode selector
        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # Record button
        self._record_button = RecordButton()
        self._record_button.connect("toggled", self._on_record_toggled)
        left_box.append(self._record_button)

        # Mode selector
        self._mode_selector = ModeSelector()
        self._mode_selector.connect("mode-changed", self._on_mode_changed)
        left_box.append(self._mode_selector)

        header.pack_start(left_box)

        # Title
        title = Gtk.Label(label="Interview Assistant")
        title.add_css_class("heading")
        header.set_title_widget(title)

        # Right side: Audio level and menu
        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # Audio level meter
        self._audio_meter = AudioLevelBar(width=80, height=6)
        right_box.append(self._audio_meter)

        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")

        # Create menu
        menu = Gio.Menu()
        menu.append("Settings", "app.settings")
        menu.append("History", "app.history")
        menu.append("About", "app.about")
        menu.append("Quit", "app.quit")
        menu_button.set_menu_model(menu)

        right_box.append(menu_button)

        header.pack_end(right_box)

        return header

    def _build_content(self) -> Gtk.Widget:
        """Build the main content area."""
        # Paned view for transcript and answer
        paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)

        # Transcript view (top)
        self._transcript_view = TranscriptView()
        self._transcript_view.set_margin_start(16)
        self._transcript_view.set_margin_end(16)
        self._transcript_view.set_margin_top(16)
        paned.set_start_child(self._transcript_view)

        # Answer view (bottom)
        self._answer_view = AnswerView()
        self._answer_view.set_margin_start(16)
        self._answer_view.set_margin_end(16)
        self._answer_view.set_margin_bottom(16)
        paned.set_end_child(self._answer_view)

        # Set initial split position
        paned.set_position(200)

        # Allow resize
        paned.set_resize_start_child(True)
        paned.set_resize_end_child(True)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)

        # Wrap in a box for proper expansion
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.set_vexpand(True)
        content_box.append(paned)

        return content_box

    def _build_status_bar(self) -> Gtk.Widget:
        """Build the status bar."""
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        status_box.set_margin_start(16)
        status_box.set_margin_end(16)
        status_box.set_margin_bottom(8)
        status_box.set_margin_top(8)

        # Status indicator
        self._status_indicator = StatusIndicator()
        status_box.append(self._status_indicator)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        status_box.append(spacer)

        # Keyboard shortcuts hint
        shortcuts_label = Gtk.Label(label="Ctrl+Alt+R: Toggle Recording")
        shortcuts_label.add_css_class("text-muted")
        status_box.append(shortcuts_label)

        return status_box

    def _connect_events(self) -> None:
        """Connect to application events."""
        self._event_bus.subscribe(Event.TRANSCRIPTION_COMPLETE, self._on_transcription_complete)
        self._event_bus.subscribe(Event.AI_ERROR, self._on_ai_error)
        self._event_bus.subscribe(Event.WINDOW_VISIBILITY_CHANGED, self._on_toggle_visibility)

    def _on_toggle_visibility(self) -> None:
        """Toggle window visibility (for hotkey)."""
        GLib.idle_add(self._toggle_visibility)

    def _toggle_visibility(self) -> None:
        """Toggle window visibility on main thread."""
        if self.get_visible():
            self.hide()
        else:
            self.present()

    def _on_window_realize(self, widget) -> None:
        """Apply stealth mode after window is realized."""
        GLib.timeout_add(500, self._apply_stealth_mode)

    def _apply_stealth_mode(self) -> bool:
        """Apply stealth mode based on config."""
        stealth_mode = self._config.stealth.mode

        if stealth_mode == StealthMode.NORMAL:
            return False

        if not is_x11_session():
            print("Stealth modes work best on X11. Wayland has limited support.")
            return False

        if self._stealth_window is None:
            self._stealth_window = X11StealthWindow(self)

        if not self._stealth_window.is_available:
            print("X11 stealth features not available (python-xlib may be missing)")
            return False

        if stealth_mode == StealthMode.OVERLAY:
            # Try popup window type - sometimes bypasses capture
            success = self._stealth_window.apply_stealth_mode('popup')
            if success:
                self._stealth_window.set_skip_taskbar(True)
                self._stealth_window.set_always_on_top(True)
                print("Stealth mode: OVERLAY (popup window type)")
            return False

        elif stealth_mode == StealthMode.SECONDARY_MONITOR:
            # Move to secondary monitor if available
            self._move_to_secondary_monitor()
            return False

        elif stealth_mode == StealthMode.HOTKEY_POPUP:
            # Hide window initially, show on hotkey
            self.hide()
            print("Stealth mode: HOTKEY_POPUP (press Ctrl+Alt+I to show)")
            return False

        return False

    def _move_to_secondary_monitor(self) -> None:
        """Move window to secondary monitor."""
        display = Gdk.Display.get_default()
        if display is None:
            return

        monitors = display.get_monitors()
        if monitors.get_n_items() < 2:
            print("Secondary monitor mode requires 2+ monitors")
            return

        # Get second monitor
        second_monitor = monitors.get_item(1)
        if second_monitor:
            geometry = second_monitor.get_geometry()
            # Move window to second monitor
            # Note: GTK4 doesn't allow direct positioning on Wayland
            # This works best on X11
            print(f"Moving to secondary monitor at ({geometry.x}, {geometry.y})")

    def _start_async_loop(self) -> None:
        """Start the async event loop in a background thread."""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

    def _on_record_toggled(self, button) -> None:
        """Handle record button toggle."""
        if button.get_active():
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self) -> None:
        """Start audio capture and transcription."""
        # Prevent multiple starts
        if self._audio_capture and self._audio_capture.is_running:
            return

        try:
            # Initialize AI assistant and warm up model
            if not self._ai_assistant:
                self._ai_assistant = get_ai_assistant()
                # Warm up AI model in background
                if self._loop:
                    async def warmup():
                        try:
                            print("Warming up AI model...")
                            await self._ai_assistant.warmup()
                            print("AI model ready")
                        except Exception as e:
                            print(f"Warmup failed: {e}")
                    asyncio.run_coroutine_threadsafe(warmup(), self._loop)

            # Initialize audio capture
            if not self._audio_capture:
                self._audio_capture = SystemAudioCapture(
                    sample_rate=16000,
                    channels=1,
                )

            # Initialize transcriber
            if not self._transcriber:
                config = StreamingConfig(
                    model_size=self._config.transcription.model_size,
                    language=self._config.transcription.language,
                )
                self._transcriber = StreamingTranscriber(config)

            # Set up audio callback to feed transcriber
            self._audio_capture.set_audio_callback(self._on_audio_data)

            # Start components
            if not self._transcriber.start():
                self._show_error("Failed to load transcription model")
                self._record_button.set_active(False)
                return

            if not self._audio_capture.start():
                self._show_error("Failed to start audio capture")
                self._record_button.set_active(False)
                return

            # Start session
            mode = self._mode_selector.get_mode()
            self._session_manager.start_session(
                InterviewType(mode.value) if hasattr(mode, 'value') else InterviewType.DSA
            )

            self._status_indicator.set_state(StatusIndicator.State.RECORDING)

        except Exception as e:
            self._show_error(f"Error starting recording: {e}")
            self._record_button.set_active(False)

    def _stop_recording(self) -> None:
        """Stop audio capture and transcription."""
        if self._audio_capture:
            self._audio_capture.stop()

        if self._transcriber:
            self._transcriber.stop()

        self._status_indicator.set_state(StatusIndicator.State.IDLE)

    def _on_audio_data(self, audio_chunk) -> None:
        """Handle incoming audio data."""
        if self._transcriber and self._transcriber.is_running:
            self._transcriber.process_audio(audio_chunk)

    def _on_mode_changed(self, selector, mode_value: str) -> None:
        """Handle interview mode change."""
        try:
            mode = AIInterviewType(mode_value)
            if self._session_manager.current_session:
                self._session_manager.current_session.set_interview_type(
                    InterviewType(mode_value)
                )
        except ValueError:
            pass

    def _on_transcription_complete(self, text: str) -> None:
        """Handle completed transcription - get AI answer."""
        if not text:
            return

        # Get AI answer asynchronously
        self._status_indicator.set_state(StatusIndicator.State.PROCESSING)

        async def get_answer():
            try:
                if not self._ai_assistant:
                    self._ai_assistant = get_ai_assistant()

                # Check if backend is available
                is_available, message = await self._ai_assistant.check_backend_available()
                if not is_available:
                    GLib.idle_add(self._show_error, f"AI Backend Error: {message}")
                    GLib.idle_add(self._status_indicator.set_state, StatusIndicator.State.ERROR)
                    return

                mode = self._mode_selector.get_mode()
                interview_type = AIInterviewType(mode.value) if hasattr(mode, 'value') else AIInterviewType.DSA

                await self._ai_assistant.get_answer(
                    text,
                    interview_type=interview_type,
                )
            except Exception as e:
                GLib.idle_add(self._show_error, f"AI Error: {e}")

        if self._loop:
            asyncio.run_coroutine_threadsafe(get_answer(), self._loop)

    def _on_ai_error(self, error_msg: str) -> None:
        """Handle AI error."""
        self._show_error(error_msg)
        self._status_indicator.set_state(StatusIndicator.State.ERROR)

    def _show_error(self, message: str) -> None:
        """Show an error message."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Error",
            body=message,
        )
        dialog.add_response("ok", "OK")
        dialog.present()

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._audio_capture:
            self._audio_capture.stop()

        if self._transcriber:
            self._transcriber.stop()

        if self._audio_meter:
            self._audio_meter.cleanup()

        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
