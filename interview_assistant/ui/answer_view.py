"""AI answer display view."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, GtkSource, Gdk, GLib, Pango

from interview_assistant.core.events import Event, get_event_bus
from interview_assistant.ai.response_parser import ResponseParser


class AnswerView(Gtk.Box):
    """
    Display AI-generated answers with syntax highlighting.

    Supports streaming responses and code block extraction.
    """

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        self.add_css_class("glass-card")

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        title = Gtk.Label(label="Answer")
        title.add_css_class("heading")
        title.set_halign(Gtk.Align.START)
        header.append(title)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header.append(spacer)

        # Copy button
        self._copy_btn = Gtk.Button()
        self._copy_btn.set_icon_name("edit-copy-symbolic")
        self._copy_btn.add_css_class("flat")
        self._copy_btn.set_tooltip_text("Copy answer")
        self._copy_btn.connect("clicked", self._on_copy_clicked)
        header.append(self._copy_btn)

        # Clear button
        clear_btn = Gtk.Button()
        clear_btn.set_icon_name("edit-clear-symbolic")
        clear_btn.add_css_class("flat")
        clear_btn.set_tooltip_text("Clear answer")
        clear_btn.connect("clicked", self._on_clear_clicked)
        header.append(clear_btn)

        self.append(header)

        # Source view for answer
        self._source_view = GtkSource.View()
        self._source_view.set_editable(False)
        self._source_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._source_view.set_show_line_numbers(False)
        self._source_view.add_css_class("answer-text")

        # Buffer with syntax highlighting capability
        self._buffer = GtkSource.Buffer()
        self._source_view.set_buffer(self._buffer)

        # Set up style scheme
        style_manager = GtkSource.StyleSchemeManager.get_default()
        for scheme_name in ["Adwaita-dark", "oblivion", "cobalt"]:
            scheme = style_manager.get_scheme(scheme_name)
            if scheme:
                self._buffer.set_style_scheme(scheme)
                break

        # Language manager for code detection
        self._lang_manager = GtkSource.LanguageManager.get_default()

        # Scrolled window
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self._source_view)
        scroll.set_vexpand(True)
        scroll.set_min_content_height(200)

        self.append(scroll)

        # Status/complexity bar
        self._status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self._status_bar.set_margin_top(8)

        self._complexity_label = Gtk.Label()
        self._complexity_label.add_css_class("text-muted")
        self._complexity_label.set_halign(Gtk.Align.START)
        self._status_bar.append(self._complexity_label)

        self.append(self._status_bar)

        # Response parser
        self._parser = ResponseParser()

        # Current response text
        self._full_response = ""

        # Subscribe to events
        self._event_bus = get_event_bus()
        self._event_bus.subscribe(Event.AI_TOKEN_RECEIVED, self._on_token_received)
        self._event_bus.subscribe(Event.AI_RESPONSE_COMPLETE, self._on_response_complete)
        self._event_bus.subscribe(Event.AI_REQUEST_STARTED, self._on_request_started)
        self._event_bus.subscribe(Event.AI_ERROR, self._on_error)

    def _on_request_started(self, question: str) -> None:
        """Handle new AI request."""
        self.clear()
        self._complexity_label.set_label("Generating answer...")

    def _on_token_received(self, token: str) -> None:
        """Handle streaming token."""
        self.append_text(token)

    def _on_response_complete(self, response) -> None:
        """Handle complete response."""
        # Extract complexity if present
        complexity = self._parser.extract_complexity(self._full_response)
        if complexity:
            time_comp, space_comp = complexity
            self._complexity_label.set_label(f"Time: {time_comp}  |  Space: {space_comp}")
        else:
            self._complexity_label.set_label("")

        # Try to detect language for highlighting
        self._detect_and_highlight()

    def _on_error(self, error_msg: str) -> None:
        """Handle AI error."""
        self.set_text(f"Error: {error_msg}")
        self._complexity_label.set_label("Error occurred")

    def _detect_and_highlight(self) -> None:
        """Detect code language and apply highlighting."""
        parsed = self._parser.parse(self._full_response)

        if parsed.code_blocks:
            # Get the primary language
            primary_lang = parsed.code_blocks[0].language
            lang = self._lang_manager.get_language(primary_lang)
            if lang:
                self._buffer.set_language(lang)

    def append_text(self, text: str) -> None:
        """
        Append text to the answer (for streaming).

        Args:
            text: Text token to append
        """
        self._full_response += text

        end_iter = self._buffer.get_end_iter()
        self._buffer.insert(end_iter, text)

        # Auto-scroll to bottom
        self._scroll_to_bottom()

    def set_text(self, text: str) -> None:
        """
        Set the entire answer text.

        Args:
            text: Complete answer text
        """
        self._full_response = text
        self._buffer.set_text(text)
        self._scroll_to_bottom()

    def get_text(self) -> str:
        """Get the current answer text."""
        return self._full_response

    def clear(self) -> None:
        """Clear the answer."""
        self._full_response = ""
        self._buffer.set_text("")
        self._buffer.set_language(None)
        self._complexity_label.set_label("")

    def _scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the view."""
        def scroll():
            adj = self._source_view.get_parent().get_vadjustment()
            adj.set_value(adj.get_upper() - adj.get_page_size())
            return False

        GLib.idle_add(scroll)

    def _on_copy_clicked(self, button) -> None:
        """Copy answer to clipboard."""
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(self._full_response)

        # Visual feedback
        button.set_icon_name("emblem-ok-symbolic")
        GLib.timeout_add(1500, lambda: button.set_icon_name("edit-copy-symbolic"))

    def _on_clear_clicked(self, button) -> None:
        """Clear the answer."""
        self.clear()

    def get_code_blocks(self) -> list:
        """Extract code blocks from the answer."""
        parsed = self._parser.parse(self._full_response)
        return [(b.language, b.code) for b in parsed.code_blocks]


class AnswerCard(Gtk.Box):
    """
    Single Q&A card for history display.
    """

    def __init__(self, question: str, answer: str, interview_type: str = "dsa"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        self.add_css_class("glass-card")
        self.set_margin_bottom(8)

        # Question
        q_label = Gtk.Label(label=f"Q: {question}")
        q_label.set_wrap(True)
        q_label.set_halign(Gtk.Align.START)
        q_label.add_css_class("transcript-text")
        self.append(q_label)

        # Separator
        sep = Gtk.Separator()
        self.append(sep)

        # Answer (truncated)
        display_answer = answer[:300] + "..." if len(answer) > 300 else answer
        a_label = Gtk.Label(label=display_answer)
        a_label.set_wrap(True)
        a_label.set_halign(Gtk.Align.START)
        a_label.add_css_class("answer-text")
        self.append(a_label)

        # Store full data
        self._question = question
        self._answer = answer
        self._interview_type = interview_type

    @property
    def question(self) -> str:
        return self._question

    @property
    def answer(self) -> str:
        return self._answer
