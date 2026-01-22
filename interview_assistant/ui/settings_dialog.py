"""Settings dialog for application configuration."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from interview_assistant.core.config import get_config, StealthMode, AIBackend
from interview_assistant.audio.devices import AudioDeviceManager
from interview_assistant.ai.ollama_client import OllamaClient


class SettingsDialog(Adw.PreferencesWindow):
    """
    Settings/preferences dialog.

    Allows configuration of:
    - API keys
    - Audio devices
    - Transcription settings
    - Stealth mode
    - UI preferences
    """

    def __init__(self, parent: Gtk.Window):
        super().__init__()

        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title("Settings")
        self.set_default_size(600, 500)

        self._config = get_config()
        self._device_manager = AudioDeviceManager()

        self._build_pages()

    def _build_pages(self) -> None:
        """Build all settings pages."""
        self.add(self._build_api_page())
        self.add(self._build_audio_page())
        self.add(self._build_transcription_page())
        self.add(self._build_stealth_page())
        self.add(self._build_ui_page())

    def _build_api_page(self) -> Adw.PreferencesPage:
        """Build AI settings page."""
        page = Adw.PreferencesPage()
        page.set_title("AI")
        page.set_icon_name("application-x-addon-symbolic")

        # Backend selection group
        backend_group = Adw.PreferencesGroup()
        backend_group.set_title("AI Backend")
        backend_group.set_description("Choose between local (Ollama) or cloud (Claude) AI")

        # Backend selector
        backend_row = Adw.ComboRow()
        backend_row.set_title("Backend")

        backends = Gtk.StringList.new([
            "Ollama (Local, Free)",
            "Claude (Cloud, Paid)",
        ])
        backend_row.set_model(backends)

        # Set current backend
        if self._config.ai.backend == AIBackend.OLLAMA:
            backend_row.set_selected(0)
        else:
            backend_row.set_selected(1)

        backend_row.connect("notify::selected", self._on_backend_changed)
        backend_group.add(backend_row)

        page.add(backend_group)

        # Ollama group
        ollama_group = Adw.PreferencesGroup()
        ollama_group.set_title("Ollama Settings")
        ollama_group.set_description("Configure local LLM with Ollama (free, offline)")

        # Ollama URL
        ollama_url_row = Adw.EntryRow()
        ollama_url_row.set_title("Ollama URL")
        ollama_url_row.set_text(self._config.ai.ollama_url)
        ollama_url_row.connect("changed", self._on_ollama_url_changed)
        ollama_group.add(ollama_url_row)

        # Ollama model
        ollama_model_row = Adw.ComboRow()
        ollama_model_row.set_title("Model")
        self._ollama_model_row = ollama_model_row

        # Default models list
        default_models = [
            "llama3.1:8b",
            "deepseek-coder-v2:16b",
            "codellama:13b",
            "mistral:7b",
            "qwen2.5-coder:7b",
        ]
        models_list = Gtk.StringList.new(default_models)
        ollama_model_row.set_model(models_list)

        # Set current model
        current = self._config.ai.ollama_model
        for i, m in enumerate(default_models):
            if m == current:
                ollama_model_row.set_selected(i)
                break

        ollama_model_row.connect("notify::selected", self._on_ollama_model_changed)
        ollama_group.add(ollama_model_row)

        # Refresh models button
        refresh_row = Adw.ActionRow()
        refresh_row.set_title("Refresh Models")
        refresh_row.set_subtitle("Scan for installed Ollama models")

        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.set_valign(Gtk.Align.CENTER)
        refresh_btn.connect("clicked", self._on_refresh_ollama_models)
        refresh_row.add_suffix(refresh_btn)
        ollama_group.add(refresh_row)

        # Status row
        self._ollama_status_row = Adw.ActionRow()
        self._ollama_status_row.set_title("Status")
        self._ollama_status_row.set_subtitle("Checking...")
        ollama_group.add(self._ollama_status_row)

        # Check Ollama status on load
        self._check_ollama_status()

        page.add(ollama_group)

        # Claude group
        claude_group = Adw.PreferencesGroup()
        claude_group.set_title("Claude Settings")
        claude_group.set_description("Configure Anthropic Claude API (requires API key)")

        # API Key entry
        api_key_row = Adw.PasswordEntryRow()
        api_key_row.set_title("API Key")
        api_key_row.set_text(self._config.ai.api_key.get_secret_value())
        api_key_row.connect("changed", self._on_api_key_changed)
        claude_group.add(api_key_row)

        # Claude model selection
        claude_model_row = Adw.ComboRow()
        claude_model_row.set_title("Model")

        claude_models = Gtk.StringList.new([
            "claude-sonnet-4-5-20250929",
            "claude-opus-4-5-20250929",
            "claude-3-5-haiku-20241022",
        ])
        claude_model_row.set_model(claude_models)

        # Set current model
        current_model = self._config.ai.claude_model
        for i, model in enumerate(["claude-sonnet-4-5-20250929", "claude-opus-4-5-20250929", "claude-3-5-haiku-20241022"]):
            if model == current_model:
                claude_model_row.set_selected(i)
                break

        claude_model_row.connect("notify::selected", self._on_claude_model_changed)
        claude_group.add(claude_model_row)

        page.add(claude_group)

        # Common settings group
        common_group = Adw.PreferencesGroup()
        common_group.set_title("Common Settings")

        # Max tokens
        tokens_row = Adw.SpinRow.new_with_range(256, 8192, 256)
        tokens_row.set_title("Max Tokens")
        tokens_row.set_value(self._config.ai.max_tokens)
        tokens_row.connect("changed", self._on_max_tokens_changed)
        common_group.add(tokens_row)

        page.add(common_group)

        return page

    def _check_ollama_status(self) -> None:
        """Check Ollama connection status."""
        import asyncio
        import threading

        def check():
            async def async_check():
                client = OllamaClient(base_url=self._config.ai.ollama_url)
                is_connected = await client.check_connection()
                if is_connected:
                    models = await client.list_models()
                    return True, models
                return False, []

            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(async_check())
            finally:
                loop.close()

        def update_ui(result):
            is_connected, models = result
            if is_connected:
                self._ollama_status_row.set_subtitle(f"Connected - {len(models)} models available")
            else:
                self._ollama_status_row.set_subtitle("Not connected - Run: ollama serve")

        def run_check():
            try:
                result = check()
                from gi.repository import GLib
                GLib.idle_add(update_ui, result)
            except Exception as e:
                from gi.repository import GLib
                GLib.idle_add(lambda: self._ollama_status_row.set_subtitle(f"Error: {e}"))

        thread = threading.Thread(target=run_check, daemon=True)
        thread.start()

    def _on_refresh_ollama_models(self, button) -> None:
        """Refresh Ollama models list."""
        import asyncio
        import threading

        def refresh():
            async def async_refresh():
                client = OllamaClient(base_url=self._config.ai.ollama_url)
                return await client.list_models()

            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(async_refresh())
            finally:
                loop.close()

        def update_ui(models):
            if models:
                model_list = Gtk.StringList.new(models)
                self._ollama_model_row.set_model(model_list)

                # Select current model if in list
                current = self._config.ai.ollama_model
                for i, m in enumerate(models):
                    if m == current:
                        self._ollama_model_row.set_selected(i)
                        break

                self._ollama_status_row.set_subtitle(f"Connected - {len(models)} models available")
            else:
                self._ollama_status_row.set_subtitle("No models found or not connected")

        def run_refresh():
            try:
                models = refresh()
                from gi.repository import GLib
                GLib.idle_add(update_ui, models)
            except Exception as e:
                from gi.repository import GLib
                GLib.idle_add(lambda: self._ollama_status_row.set_subtitle(f"Error: {e}"))

        thread = threading.Thread(target=run_refresh, daemon=True)
        thread.start()

    def _on_backend_changed(self, row, _) -> None:
        """Handle backend change."""
        backends = [AIBackend.OLLAMA, AIBackend.CLAUDE]
        self._config.ai.backend = backends[row.get_selected()]
        self._save_config()

    def _on_ollama_url_changed(self, entry) -> None:
        """Handle Ollama URL change."""
        self._config.ai.ollama_url = entry.get_text()
        self._save_config()

    def _on_ollama_model_changed(self, row, _) -> None:
        """Handle Ollama model change."""
        model = row.get_model()
        if model:
            selected = row.get_selected()
            if 0 <= selected < model.get_n_items():
                self._config.ai.ollama_model = model.get_string(selected)
                self._save_config()

    def _on_claude_model_changed(self, row, _) -> None:
        """Handle Claude model change."""
        models = ["claude-sonnet-4-5-20250929", "claude-opus-4-5-20250929", "claude-3-5-haiku-20241022"]
        self._config.ai.claude_model = models[row.get_selected()]
        self._save_config()

    def _build_audio_page(self) -> Adw.PreferencesPage:
        """Build audio settings page."""
        page = Adw.PreferencesPage()
        page.set_title("Audio")
        page.set_icon_name("audio-input-microphone-symbolic")

        group = Adw.PreferencesGroup()
        group.set_title("Audio Capture")
        group.set_description("Configure system audio capture")

        # Device selection
        device_row = Adw.ComboRow()
        device_row.set_title("Capture Device")

        # Get monitor devices
        monitors = self._device_manager.get_monitor_devices()
        device_names = ["Auto (Default Monitor)"] + [d.display_name for d in monitors]

        devices_list = Gtk.StringList.new(device_names)
        device_row.set_model(devices_list)

        device_row.connect("notify::selected", self._on_device_changed)
        group.add(device_row)

        # Refresh button
        refresh_row = Adw.ActionRow()
        refresh_row.set_title("Refresh Devices")
        refresh_row.set_subtitle("Scan for new audio devices")

        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.set_valign(Gtk.Align.CENTER)
        refresh_btn.connect("clicked", lambda _: self._device_manager.refresh_devices())
        refresh_row.add_suffix(refresh_btn)
        group.add(refresh_row)

        page.add(group)
        return page

    def _build_transcription_page(self) -> Adw.PreferencesPage:
        """Build transcription settings page."""
        page = Adw.PreferencesPage()
        page.set_title("Transcription")
        page.set_icon_name("audio-x-generic-symbolic")

        group = Adw.PreferencesGroup()
        group.set_title("Whisper Settings")
        group.set_description("Configure speech-to-text transcription")

        # Model size
        model_row = Adw.ComboRow()
        model_row.set_title("Model Size")

        models = Gtk.StringList.new([
            "tiny (fastest, less accurate)",
            "base (balanced)",
            "small (more accurate)",
            "medium (high accuracy)",
            "large-v3 (best, slow)",
        ])
        model_row.set_model(models)

        model_sizes = ["tiny", "base", "small", "medium", "large-v3"]
        current = self._config.transcription.model_size
        for i, size in enumerate(model_sizes):
            if size == current:
                model_row.set_selected(i)
                break

        model_row.connect("notify::selected", self._on_whisper_model_changed)
        group.add(model_row)

        # Language
        lang_row = Adw.EntryRow()
        lang_row.set_title("Language")
        lang_row.set_text(self._config.transcription.language)
        lang_row.connect("changed", self._on_language_changed)
        group.add(lang_row)

        # Device (CPU/CUDA)
        device_row = Adw.ComboRow()
        device_row.set_title("Compute Device")

        devices = Gtk.StringList.new(["Auto", "CPU", "CUDA (GPU)"])
        device_row.set_model(devices)
        device_row.connect("notify::selected", self._on_compute_device_changed)
        group.add(device_row)

        page.add(group)
        return page

    def _build_stealth_page(self) -> Adw.PreferencesPage:
        """Build stealth settings page."""
        page = Adw.PreferencesPage()
        page.set_title("Stealth")
        page.set_icon_name("security-high-symbolic")

        group = Adw.PreferencesGroup()
        group.set_title("Screen-Share Avoidance")
        group.set_description("Configure how the app hides during screen sharing")

        # Stealth mode
        mode_row = Adw.ComboRow()
        mode_row.set_title("Stealth Mode")

        modes = Gtk.StringList.new([
            "Normal (No stealth)",
            "Overlay (X11 window tricks)",
            "Secondary Monitor Only",
            "Hotkey Popup (Auto-hide)",
        ])
        mode_row.set_model(modes)

        mode_values = [StealthMode.NORMAL, StealthMode.OVERLAY,
                      StealthMode.SECONDARY_MONITOR, StealthMode.HOTKEY_POPUP]
        current = self._config.stealth.mode
        for i, mode in enumerate(mode_values):
            if mode == current:
                mode_row.set_selected(i)
                break

        mode_row.connect("notify::selected", self._on_stealth_mode_changed)
        group.add(mode_row)

        # Auto-hide timeout
        timeout_row = Adw.SpinRow.new_with_range(1000, 30000, 1000)
        timeout_row.set_title("Auto-hide Timeout (ms)")
        timeout_row.set_value(self._config.stealth.auto_hide_timeout)
        timeout_row.connect("changed", self._on_timeout_changed)
        group.add(timeout_row)

        # Opacity
        opacity_row = Adw.SpinRow.new_with_range(0.3, 1.0, 0.05)
        opacity_row.set_title("Window Opacity")
        opacity_row.set_value(self._config.stealth.opacity)
        opacity_row.connect("changed", self._on_opacity_changed)
        group.add(opacity_row)

        # Always on top
        on_top_row = Adw.SwitchRow()
        on_top_row.set_title("Always on Top")
        on_top_row.set_active(self._config.stealth.always_on_top)
        on_top_row.connect("notify::active", self._on_always_on_top_changed)
        group.add(on_top_row)

        page.add(group)

        # Warning group
        warning_group = Adw.PreferencesGroup()
        warning_group.set_title("Important Notes")

        warning_row = Adw.ActionRow()
        warning_row.set_title("No Guaranteed Stealth")
        warning_row.set_subtitle(
            "These techniques may not work with all screen capture tools. "
            "Secondary monitor mode is most reliable if you share only your primary display."
        )
        warning_group.add(warning_row)

        page.add(warning_group)
        return page

    def _build_ui_page(self) -> Adw.PreferencesPage:
        """Build UI settings page."""
        page = Adw.PreferencesPage()
        page.set_title("Appearance")
        page.set_icon_name("applications-graphics-symbolic")

        group = Adw.PreferencesGroup()
        group.set_title("Theme")

        # Font size
        font_row = Adw.SpinRow.new_with_range(10, 20, 1)
        font_row.set_title("Font Size")
        font_row.set_value(self._config.ui.font_size)
        font_row.connect("changed", self._on_font_size_changed)
        group.add(font_row)

        page.add(group)
        return page

    # Event handlers
    def _on_api_key_changed(self, entry) -> None:
        from pydantic import SecretStr
        self._config.ai.api_key = SecretStr(entry.get_text())
        self._save_config()


    def _on_max_tokens_changed(self, row) -> None:
        self._config.ai.max_tokens = int(row.get_value())
        self._save_config()

    def _on_device_changed(self, row, _) -> None:
        # Handle device change
        pass

    def _on_whisper_model_changed(self, row, _) -> None:
        models = ["tiny", "base", "small", "medium", "large-v3"]
        self._config.transcription.model_size = models[row.get_selected()]
        self._save_config()

    def _on_language_changed(self, entry) -> None:
        self._config.transcription.language = entry.get_text()
        self._save_config()

    def _on_compute_device_changed(self, row, _) -> None:
        devices = ["auto", "cpu", "cuda"]
        self._config.transcription.device = devices[row.get_selected()]
        self._save_config()

    def _on_stealth_mode_changed(self, row, _) -> None:
        modes = [StealthMode.NORMAL, StealthMode.OVERLAY,
                StealthMode.SECONDARY_MONITOR, StealthMode.HOTKEY_POPUP]
        self._config.stealth.mode = modes[row.get_selected()]
        self._save_config()

    def _on_timeout_changed(self, row) -> None:
        self._config.stealth.auto_hide_timeout = int(row.get_value())
        self._save_config()

    def _on_opacity_changed(self, row) -> None:
        self._config.stealth.opacity = row.get_value()
        self._save_config()

    def _on_always_on_top_changed(self, row, _) -> None:
        self._config.stealth.always_on_top = row.get_active()
        self._save_config()

    def _on_font_size_changed(self, row) -> None:
        self._config.ui.font_size = int(row.get_value())
        self._save_config()

    def _save_config(self) -> None:
        """Save configuration to file."""
        try:
            self._config.save()
        except Exception as e:
            print(f"Error saving config: {e}")
