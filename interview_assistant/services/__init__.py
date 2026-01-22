"""System services for Interview Assistant."""

from .tray import SystemTray
from .shortcuts import ShortcutManager
from .web_viewer import WebViewer, get_web_viewer

__all__ = [
    "SystemTray",
    "ShortcutManager",
    "WebViewer",
    "get_web_viewer",
]
