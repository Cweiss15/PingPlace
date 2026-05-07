"""
services/device_service.py — Device Service

Handles creating and finding devices (users identified by cookie).

This is the business logic for user identification:
- First visit? Create a new device, return its cookie token.
- Returning? Look up the device by cookie token, update last_seen.
"""

from datetime import datetime, timezone
from extensions import db
from models.device import Device


def get_or_create_device(cookie_token):
    """
    Find an existing device by its cookie token, or create a new one.

    Args:
        cookie_token: The UUID string from the browser cookie (or None if first visit)

    Returns:
        Device object (either existing or freshly created)

    How it works:
        1. If cookie_token is provided, search the database for a matching device
        2. If found, update last_seen_at timestamp and return it
        3. If not found (or no token provided), create a new device
    """
    if cookie_token:
        # Try to find existing device with this cookie
        device = Device.query.filter_by(cookie_token=cookie_token).first()

        if device:
            # Found! Update the "last seen" timestamp
            device.last_seen_at = datetime.now(timezone.utc)
            db.session.commit()
            return device

    # No cookie or device not found — create a new one
    new_device = Device()
    db.session.add(new_device)    # Stage for saving
    db.session.commit()           # Actually write to database
    return new_device


def get_device_by_id(device_id):
    """
    Look up a device by its primary key ID.

    Args:
        device_id: The UUID string of the device

    Returns:
        Device object or None if not found
    """
    return Device.query.get(device_id)


def get_device_by_cookie(cookie_token):
    """
    Look up a device by its cookie token WITHOUT creating a new one.

    Used by protected endpoints — if cookie is missing/invalid, returns None
    so the endpoint can return a 401 Unauthorized response.

    Args:
        cookie_token: The UUID string from the browser cookie

    Returns:
        Device object or None if not found
    """
    if not cookie_token:
        return None
    device = Device.query.filter_by(cookie_token=cookie_token).first()
    if device:
        # Update last-seen timestamp
        device.last_seen_at = datetime.now(timezone.utc)
        db.session.commit()
    return device
