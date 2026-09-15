"""Compatibility import for older scripts; use :mod:`src.config.settings`."""

from src.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
