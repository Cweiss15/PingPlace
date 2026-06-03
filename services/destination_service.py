"""
services/destination_service.py — Destination Service

CRUD operations for saved destinations.
CRUD = Create, Read, Update, Delete — the four basic database operations.

This service handles:
- Adding a new destination (from Google Places selection)
- Listing all destinations for a device
- Updating a destination (change name or threshold)
- Deleting a destination
"""

from extensions import db
from models.destination import Destination


def create_destination(device_id, name, address, place_id, latitude, longitude,
                       alert_threshold_minutes=10):
    """
    Save a new destination for a device.

    Args:
        device_id: UUID of the device that owns this destination
        name: User's label (e.g., "Home")
        address: Full address from Google Places
        place_id: Google's unique identifier for this place
        latitude: GPS latitude
        longitude: GPS longitude
        alert_threshold_minutes: Minutes before arrival to alert (default 10)

    Returns:
        The newly created Destination object
    """
    destination = Destination(
        device_id=device_id,
        name=name,
        address=address,
        place_id=place_id,
        latitude=latitude,
        longitude=longitude,
        alert_threshold_minutes=alert_threshold_minutes,
    )
    db.session.add(destination)
    db.session.commit()
    return destination


def list_destinations(device_id):
    """
    Get all saved destinations for a device.

    Args:
        device_id: UUID of the device

    Returns:
        List of Destination objects (could be empty)
    """
    return Destination.query.filter_by(device_id=device_id).all()


def get_destination(destination_id, device_id):
    """
    Get a single destination, verifying it belongs to the requesting device.

    Why verify device_id? Security — prevents one user from accessing
    another user's destinations by guessing IDs (IDOR prevention).

    Args:
        destination_id: UUID of the destination
        device_id: UUID of the requesting device (for ownership check)

    Returns:
        Destination object or None
    """
    return Destination.query.filter_by(
        id=destination_id,
        device_id=device_id
    ).first()


def update_destination(destination_id, device_id, **kwargs):
    """
    Update a destination's fields.

    Args:
        destination_id: UUID of the destination to update
        device_id: UUID of the requesting device (ownership check)
        **kwargs: Fields to update (e.g., name="New Name", alert_threshold_minutes=15)

    Returns:
        Updated Destination object, or None if not found

    The **kwargs pattern means "any keyword arguments". So you can call:
        update_destination(id, device_id, name="Office", alert_threshold_minutes=5)
    """
    destination = get_destination(destination_id, device_id)
    if not destination:
        return None

    allowed_fields = ['name', 'alert_threshold_minutes']
    for field, value in kwargs.items():
        if field in allowed_fields and value is not None:
            setattr(destination, field, value)

    db.session.commit()
    return destination


def delete_destination(destination_id, device_id):
    """
    Delete a destination (with ownership verification).

    Args:
        destination_id: UUID of the destination to delete
        device_id: UUID of the requesting device (ownership check)

    Returns:
        True if deleted, False if not found
    """
    destination = get_destination(destination_id, device_id)
    if not destination:
        return False

    db.session.delete(destination)
    db.session.commit()
    return True
