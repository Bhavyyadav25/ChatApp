#!/usr/bin/env python3
"""Entry point for Interview Assistant."""

import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from interview_assistant.app import InterviewAssistantApp


def main():
    """Main entry point."""
    app = InterviewAssistantApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
