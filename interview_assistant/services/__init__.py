"""System services for Interview Assistant."""

from .tray import SystemTray
from .shortcuts import ShortcutManager

__all__ = [
    "SystemTray",
    "ShortcutManager",
]
