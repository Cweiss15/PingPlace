"""
models/__init__.py — Makes this folder a Python package.

When Python sees a folder with __init__.py, it treats the folder
as a "package" you can import from. This file also conveniently
exports all models so other files can do:
    from models import Device, Destination, AlertSession
"""

from models.device import Device
from models.destination import Destination
from models.alert_session import AlertSession

__all__ = ['Device', 'Destination', 'AlertSession']
