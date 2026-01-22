"""Code block widget with syntax highlighting."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, GtkSource, Gdk, GLib


class CodeBlockView(Gtk.Box):
    """
    Code block display with syntax highlighting.

    Uses GtkSourceView for proper code highlighting.
    """

    def __init__(self, language: str = "python", code: str = ""):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self.add_css_class("code-block")

        # Header with language label and copy button
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header.add_css_class("code-header")

        self._language_label = Gtk.Label(label=language.upper())
        self._language_label.add_css_class("label-small")
        header.append(self._language_label)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header.append(spacer)

        # Copy button
        copy_button = Gtk.Button()
        copy_button.set_icon_name("edit-copy-symbolic")
        copy_button.add_css_class("flat")
        copy_button.set_tooltip_text("Copy code")
        copy_button.connect("clicked", self._on_copy_clicked)
        header.append(copy_button)

        self.append(header)

        # Source view
        self._source_view = GtkSource.View()
        self._source_view.set_editable(False)
        self._source_view.set_show_line_numbers(True)
        self._source_view.set_highlight_current_line(False)
        self._source_view.set_monospace(True)
        self._source_view.add_css_class("answer-text")

        # Configure view
        self._source_view.set_tab_width(4)
        self._source_view.set_indent_width(4)
        self._source_view.set_auto_indent(True)

        # Buffer
        self._buffer = GtkSource.Buffer()
        self._source_view.set_buffer(self._buffer)

        # Set up language manager
        self._lang_manager = GtkSource.LanguageManager.get_default()

        # Set up style scheme (dark theme)
        style_manager = GtkSource.StyleSchemeManager.get_default()
        # Try different dark schemes
        for scheme_name in ["Adwaita-dark", "oblivion", "cobalt", "classic-dark"]:
            scheme = style_manager.get_scheme(scheme_name)
            if scheme:
                self._buffer.set_style_scheme(scheme)
                break

        # Scrolled window
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self._source_view)
        scroll.set_vexpand(True)
        scroll.set_min_content_height(100)
        scroll.set_max_content_height(400)

        self.append(scroll)

        # Set initial content
        if code:
            self.set_code(code, language)

    def set_code(self, code: str, language: str = "python") -> None:
        """
        Set the code content.

        Args:
            code: Code text
            language: Programming language for highlighting
        """
        # Update language label
        self._language_label.set_label(language.upper())

        # Set language for highlighting
        lang = self._lang_manager.get_language(language)
        if lang:
            self._buffer.set_language(lang)
        else:
            # Try to guess language
            lang = self._lang_manager.guess_language(None, f"text/{language}")
            if lang:
                self._buffer.set_language(lang)

        # Set text
        self._buffer.set_text(code)

    def get_code(self) -> str:
        """Get the code content."""
        start = self._buffer.get_start_iter()
        end = self._buffer.get_end_iter()
        return self._buffer.get_text(start, end, True)

    def _on_copy_clicked(self, button) -> None:
        """Copy code to clipboard."""
        clipboard = Gdk.Display.get_default().get_clipboard()
        code = self.get_code()
        clipboard.set(code)

        # Visual feedback
        button.set_icon_name("emblem-ok-symbolic")
        GLib.timeout_add(1500, lambda: button.set_icon_name("edit-copy-symbolic"))


class InlineCode(Gtk.Label):
    """
    Inline code span widget.
    """

    def __init__(self, code: str = ""):
        super().__init__(label=code)

        self.add_css_class("code-inline")
        self.set_selectable(True)

    def set_code(self, code: str) -> None:
        """Set the code text."""
        self.set_label(code)


class CodeBlockContainer(Gtk.Box):
    """
    Container that can hold multiple code blocks.

    Useful for displaying multiple code snippets.
    """

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        self._blocks = []

    def add_code_block(self, code: str, language: str = "python") -> CodeBlockView:
        """
        Add a code block.

        Args:
            code: Code content
            language: Programming language

        Returns:
            The created CodeBlockView
        """
        block = CodeBlockView(language, code)
        self._blocks.append(block)
        self.append(block)
        return block

    def clear(self) -> None:
        """Remove all code blocks."""
        for block in self._blocks:
            self.remove(block)
        self._blocks = []

    def get_all_code(self) -> list:
        """Get all code blocks as list of (language, code) tuples."""
        return [(b._language_label.get_label().lower(), b.get_code())
                for b in self._blocks]
