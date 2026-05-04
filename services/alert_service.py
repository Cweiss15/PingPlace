"""
services/alert_service.py — Alert Service

Manages the lifecycle of alert sessions:
1. Start alert → creates AlertSession in database
2. Stop alert → marks AlertSession as ended
3. Record fire → marks that the alert actually triggered

This service only handles the DATABASE side of alerts.
The actual polling and notification logic lives in the frontend JavaScript.

Why? Because:
- GPS comes from the browser (Geolocation API)
- Notifications fire from the browser (Notification API)
- Audio plays in the browser (Web Audio API)
- The server just calculates ETA and records history
"""

from datetime import datetime, timezone
from app import db
from models.alert_session import AlertSession


def start_alert(device_id, destination_id):
    """
    Create a new alert session when user taps "Start Alert".

    Args:
        device_id: UUID of the device
        destination_id: UUID of the destination being monitored

    Returns:
        The new AlertSession object
    """
    # End any existing active alert for this device first
    # (Business Rule BR-01: only one active alert at a time)
    stop_active_alerts(device_id)

    session = AlertSession(
        device_id=device_id,
        destination_id=destination_id
    )
    db.session.add(session)
    db.session.commit()
    return session


def stop_alert(session_id, device_id, reason='user_stopped'):
    """
    End an alert session.

    Args:
        session_id: UUID of the alert session to stop
        device_id: UUID of the device (ownership check)
        reason: Why it stopped — 'user_stopped', 'alert_fired', or 'error'

    Returns:
        The updated AlertSession, or None if not found
    """
    session = AlertSession.query.filter_by(
        id=session_id,
        device_id=device_id
    ).first()

    if not session:
        return None

    session.ended_at = datetime.now(timezone.utc)

    if reason == 'alert_fired':
        session.alert_fired = True
        session.alert_fired_at = datetime.now(timezone.utc)

    db.session.commit()
    return session


def stop_active_alerts(device_id):
    """
    Stop ALL active alerts for a device.
    An "active" alert is one where ended_at is NULL (hasn't been stopped yet).

    Used to enforce BR-01: only one alert at a time.
    """
    active_sessions = AlertSession.query.filter_by(
        device_id=device_id,
        ended_at=None
    ).all()

    for session in active_sessions:
        session.ended_at = datetime.now(timezone.utc)

    if active_sessions:
        db.session.commit()


def get_active_alert(device_id):
    """
    Get the currently active alert for a device (if any).

    Returns:
        AlertSession with ended_at=None, or None if no active alert
    """
    return AlertSession.query.filter_by(
        device_id=device_id,
        ended_at=None
    ).first()
