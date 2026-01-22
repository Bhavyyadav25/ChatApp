"""Live transcript display view."""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Pango

from interview_assistant.core.events import Event, get_event_bus


class TranscriptView(Gtk.Box):
    """
    Live transcript display showing the interviewer's questions.

    Updates in real-time as speech is transcribed.
    """

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        self.add_css_class("glass-card")

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        title = Gtk.Label(label="Interviewer")
        title.add_css_class("heading")
        title.set_halign(Gtk.Align.START)
        header.append(title)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header.append(spacer)

        # Clear button
        clear_btn = Gtk.Button()
        clear_btn.set_icon_name("edit-clear-symbolic")
        clear_btn.add_css_class("flat")
        clear_btn.set_tooltip_text("Clear transcript")
        clear_btn.connect("clicked", self._on_clear_clicked)
        header.append(clear_btn)

        self.append(header)

        # Transcript text view
        self._text_view = Gtk.TextView()
        self._text_view.set_editable(False)
        self._text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._text_view.set_cursor_visible(False)
        self._text_view.add_css_class("transcript-text")

        self._buffer = self._text_view.get_buffer()

        # Scrolled window
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self._text_view)
        scroll.set_vexpand(True)
        scroll.set_min_content_height(100)

        self.append(scroll)

        # Status label
        self._status_label = Gtk.Label(label="Waiting for audio...")
        self._status_label.add_css_class("text-muted")
        self._status_label.set_halign(Gtk.Align.START)
        self.append(self._status_label)

        # Subscribe to events
        self._event_bus = get_event_bus()
        self._event_bus.subscribe(Event.TRANSCRIPTION_STARTED, self._on_transcription_started)
        self._event_bus.subscribe(Event.TRANSCRIPTION_PARTIAL, self._on_partial_transcript)
        self._event_bus.subscribe(Event.TRANSCRIPTION_COMPLETE, self._on_transcript_complete)
        self._event_bus.subscribe(Event.RECORDING_STARTED, self._on_recording_started)
        self._event_bus.subscribe(Event.RECORDING_STOPPED, self._on_recording_stopped)

    def _on_transcription_started(self, _) -> None:
        """Handle transcription started."""
        self._status_label.set_label("Listening...")

    def _on_partial_transcript(self, text: str) -> None:
        """Handle partial transcription update."""
        # Could show partial text in a different style
        pass

    def _on_transcript_complete(self, text: str) -> None:
        """Handle complete transcription."""
        if text:
            self.append_text(text)
            self._status_label.set_label("Question detected")

    def _on_recording_started(self, _) -> None:
        """Handle recording started."""
        self._status_label.set_label("Recording...")

    def _on_recording_stopped(self, _) -> None:
        """Handle recording stopped."""
        self._status_label.set_label("Recording stopped")

    def _on_clear_clicked(self, button) -> None:
        """Clear the transcript."""
        self.clear()

    def append_text(self, text: str) -> None:
        """
        Append text to the transcript.

        Args:
            text: Text to append
        """
        end_iter = self._buffer.get_end_iter()

        # Add timestamp or separator if not empty
        if self._buffer.get_char_count() > 0:
            self._buffer.insert(end_iter, "\n\n")
            end_iter = self._buffer.get_end_iter()

        # Insert the text
        self._buffer.insert(end_iter, f"Q: {text}")

        # Scroll to bottom
        self._scroll_to_bottom()

    def set_text(self, text: str) -> None:
        """
        Set the entire transcript text.

        Args:
            text: Full transcript text
        """
        self._buffer.set_text(text)
        self._scroll_to_bottom()

    def get_text(self) -> str:
        """Get the current transcript text."""
        start = self._buffer.get_start_iter()
        end = self._buffer.get_end_iter()
        return self._buffer.get_text(start, end, True)

    def get_last_question(self) -> str:
        """Get the most recent question."""
        text = self.get_text()
        if not text:
            return ""

        # Split by "Q:" markers
        parts = text.split("Q:")
        if len(parts) > 1:
            return parts[-1].strip()
        return text.strip()

    def clear(self) -> None:
        """Clear the transcript."""
        self._buffer.set_text("")
        self._status_label.set_label("Transcript cleared")

    def _scroll_to_bottom(self) -> None:
        """Scroll the text view to the bottom."""
        def scroll():
            adj = self._text_view.get_parent().get_vadjustment()
            adj.set_value(adj.get_upper() - adj.get_page_size())
            return False

        GLib.idle_add(scroll)


class TranscriptHistory(Gtk.Box):
    """
    Transcript history showing past questions.

    Displays a list of previous questions with timestamps.
    """

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        self._questions = []

        # List box for questions
        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.add_css_class("glass-surface")

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self._list_box)
        scroll.set_vexpand(True)

        self.append(scroll)

        # Subscribe to events
        self._event_bus = get_event_bus()
        self._event_bus.subscribe(Event.TRANSCRIPTION_COMPLETE, self._on_new_question)

    def _on_new_question(self, text: str) -> None:
        """Handle new question."""
        if text:
            self.add_question(text)

    def add_question(self, text: str) -> None:
        """Add a question to history."""
        from datetime import datetime

        self._questions.append({
            'text': text,
            'time': datetime.now(),
        })

        # Create row
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)

        # Question text (truncated)
        display_text = text[:100] + "..." if len(text) > 100 else text
        label = Gtk.Label(label=display_text)
        label.set_halign(Gtk.Align.START)
        label.set_wrap(True)
        label.add_css_class("transcript-text")
        box.append(label)

        # Timestamp
        time_str = datetime.now().strftime("%H:%M:%S")
        time_label = Gtk.Label(label=time_str)
        time_label.set_halign(Gtk.Align.START)
        time_label.add_css_class("text-muted")
        box.append(time_label)

        row.set_child(box)
        self._list_box.append(row)

    def clear(self) -> None:
        """Clear all history."""
        self._questions = []
        while True:
            row = self._list_box.get_row_at_index(0)
            if row:
                self._list_box.remove(row)
            else:
                break

    def get_questions(self) -> list:
        """Get all questions."""
        return self._questions.copy()
