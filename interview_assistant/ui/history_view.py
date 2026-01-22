"""History view for past Q&A pairs."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GLib

from datetime import datetime
from typing import List, Optional

from interview_assistant.core.events import Event, get_event_bus
from interview_assistant.core.session import QAPair


class HistoryDialog(Adw.Window):
    """
    Dialog showing Q&A history.

    Allows browsing, searching, and exporting past questions and answers.
    """

    def __init__(self, parent: Gtk.Window):
        super().__init__()

        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title("History")
        self.set_default_size(700, 500)

        self._event_bus = get_event_bus()
        self._history: List[QAPair] = []

        self._build_ui()
        self._connect_events()

    def _build_ui(self) -> None:
        """Build the history UI."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Header bar
        header = Adw.HeaderBar()

        # Search button
        search_btn = Gtk.ToggleButton()
        search_btn.set_icon_name("system-search-symbolic")
        search_btn.connect("toggled", self._on_search_toggled)
        header.pack_start(search_btn)

        # Export button
        export_btn = Gtk.Button()
        export_btn.set_icon_name("document-save-symbolic")
        export_btn.set_tooltip_text("Export history")
        export_btn.connect("clicked", self._on_export_clicked)
        header.pack_end(export_btn)

        # Clear button
        clear_btn = Gtk.Button()
        clear_btn.set_icon_name("edit-clear-all-symbolic")
        clear_btn.set_tooltip_text("Clear history")
        clear_btn.connect("clicked", self._on_clear_clicked)
        header.pack_end(clear_btn)

        main_box.append(header)

        # Search bar
        self._search_bar = Gtk.SearchBar()
        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_hexpand(True)
        self._search_entry.connect("search-changed", self._on_search_changed)
        self._search_bar.set_child(self._search_entry)
        main_box.append(self._search_bar)

        # Content area with list and detail view
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)

        # List of Q&A items
        list_box_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        list_box_container.set_size_request(250, -1)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.connect("row-selected", self._on_row_selected)
        self._list_box.add_css_class("glass-surface")

        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_child(self._list_box)
        list_scroll.set_vexpand(True)
        list_box_container.append(list_scroll)

        paned.set_start_child(list_box_container)

        # Detail view
        detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        detail_box.set_margin_top(12)
        detail_box.set_margin_bottom(12)
        detail_box.set_margin_start(12)
        detail_box.set_margin_end(12)

        # Question section
        q_label = Gtk.Label(label="Question")
        q_label.add_css_class("heading")
        q_label.set_halign(Gtk.Align.START)
        detail_box.append(q_label)

        self._question_view = Gtk.TextView()
        self._question_view.set_editable(False)
        self._question_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._question_view.add_css_class("transcript-text")

        q_scroll = Gtk.ScrolledWindow()
        q_scroll.set_child(self._question_view)
        q_scroll.set_min_content_height(80)
        detail_box.append(q_scroll)

        # Answer section
        a_label = Gtk.Label(label="Answer")
        a_label.add_css_class("heading")
        a_label.set_halign(Gtk.Align.START)
        detail_box.append(a_label)

        self._answer_view = Gtk.TextView()
        self._answer_view.set_editable(False)
        self._answer_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._answer_view.add_css_class("answer-text")

        a_scroll = Gtk.ScrolledWindow()
        a_scroll.set_child(self._answer_view)
        a_scroll.set_vexpand(True)
        detail_box.append(a_scroll)

        # Action buttons
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        copy_q_btn = Gtk.Button(label="Copy Question")
        copy_q_btn.connect("clicked", self._on_copy_question)
        action_box.append(copy_q_btn)

        copy_a_btn = Gtk.Button(label="Copy Answer")
        copy_a_btn.connect("clicked", self._on_copy_answer)
        action_box.append(copy_a_btn)

        detail_box.append(action_box)

        paned.set_end_child(detail_box)
        paned.set_position(250)

        main_box.append(paned)

        self.set_content(main_box)

    def _connect_events(self) -> None:
        """Connect to events."""
        self._event_bus.subscribe(Event.HISTORY_UPDATED, self._on_history_updated)

    def _on_history_updated(self, history: List[QAPair]) -> None:
        """Handle history update."""
        self._history = history
        self._refresh_list()

    def _refresh_list(self) -> None:
        """Refresh the list of Q&A items."""
        # Clear existing items
        while True:
            row = self._list_box.get_row_at_index(0)
            if row:
                self._list_box.remove(row)
            else:
                break

        # Add items
        for qa in reversed(self._history):  # Most recent first
            row = self._create_list_row(qa)
            self._list_box.append(row)

    def _create_list_row(self, qa: QAPair) -> Gtk.ListBoxRow:
        """Create a list row for a Q&A pair."""
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)

        # Question preview
        preview = qa.question[:50] + "..." if len(qa.question) > 50 else qa.question
        q_label = Gtk.Label(label=preview)
        q_label.set_halign(Gtk.Align.START)
        q_label.set_wrap(True)
        q_label.add_css_class("transcript-text")
        box.append(q_label)

        # Timestamp and type
        meta_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        time_label = Gtk.Label(label=qa.timestamp.strftime("%H:%M:%S"))
        time_label.add_css_class("text-muted")
        meta_box.append(time_label)

        type_label = Gtk.Label(label=qa.interview_type.value.upper())
        type_label.add_css_class("badge")
        type_label.add_css_class(qa.interview_type.value.replace("_", "-"))
        meta_box.append(type_label)

        box.append(meta_box)

        row.set_child(box)
        row._qa_data = qa  # Store reference

        return row

    def _on_row_selected(self, list_box, row) -> None:
        """Handle row selection."""
        if row and hasattr(row, '_qa_data'):
            qa = row._qa_data
            self._question_view.get_buffer().set_text(qa.question)
            self._answer_view.get_buffer().set_text(qa.answer)

    def _on_search_toggled(self, button) -> None:
        """Handle search toggle."""
        self._search_bar.set_search_mode(button.get_active())
        if button.get_active():
            self._search_entry.grab_focus()

    def _on_search_changed(self, entry) -> None:
        """Handle search text change."""
        query = entry.get_text().lower()
        if not query:
            self._refresh_list()
            return

        # Filter history
        filtered = [
            qa for qa in self._history
            if query in qa.question.lower() or query in qa.answer.lower()
        ]

        # Update list
        while True:
            row = self._list_box.get_row_at_index(0)
            if row:
                self._list_box.remove(row)
            else:
                break

        for qa in reversed(filtered):
            row = self._create_list_row(qa)
            self._list_box.append(row)

    def _on_export_clicked(self, button) -> None:
        """Handle export button click."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Export History")
        dialog.set_initial_name("interview_history.md")

        dialog.save(self, None, self._on_export_response)

    def _on_export_response(self, dialog, result) -> None:
        """Handle export file dialog response."""
        try:
            file = dialog.save_finish(result)
            if file:
                path = file.get_path()
                self._export_to_file(path)
        except Exception as e:
            print(f"Export error: {e}")

    def _export_to_file(self, path: str) -> None:
        """Export history to file."""
        content = "# Interview History\n\n"

        for qa in self._history:
            content += f"## {qa.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            content += f"**Type:** {qa.interview_type.value}\n\n"
            content += f"### Question\n{qa.question}\n\n"
            content += f"### Answer\n{qa.answer}\n\n"
            content += "---\n\n"

        with open(path, 'w') as f:
            f.write(content)

    def _on_clear_clicked(self, button) -> None:
        """Handle clear button click."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Clear History?",
            body="This will delete all saved questions and answers.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("clear", "Clear")
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_clear_response)
        dialog.present()

    def _on_clear_response(self, dialog, response) -> None:
        """Handle clear confirmation response."""
        if response == "clear":
            self._history = []
            self._refresh_list()
            self._question_view.get_buffer().set_text("")
            self._answer_view.get_buffer().set_text("")
            self._event_bus.emit(Event.HISTORY_CLEARED)

    def _on_copy_question(self, button) -> None:
        """Copy question to clipboard."""
        buffer = self._question_view.get_buffer()
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end, True)

        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(text)

    def _on_copy_answer(self, button) -> None:
        """Copy answer to clipboard."""
        buffer = self._answer_view.get_buffer()
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end, True)

        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(text)

    def add_qa(self, qa: QAPair) -> None:
        """Add a Q&A pair to history."""
        self._history.append(qa)
        self._refresh_list()

    def set_history(self, history: List[QAPair]) -> None:
        """Set the full history."""
        self._history = history
        self._refresh_list()
