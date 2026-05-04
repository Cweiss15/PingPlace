"""
routes/alert_routes.py — Alert Management Routes

Endpoints for starting and stopping alert sessions.
These record alert activity in the database for history/debugging.

Endpoints:
    POST /api/alert/start  → Start monitoring (creates AlertSession)
    POST /api/alert/stop   → Stop monitoring (ends AlertSession)
    GET  /api/alert/active → Get current active alert (if any)
"""

from flask import Blueprint, request, jsonify
from services import alert_service, device_service, destination_service
from app import limiter

alert_bp = Blueprint('alert', __name__)


@alert_bp.route('/alert/start', methods=['POST'])
@limiter.limit("10 per minute")
def start_alert():
    """
    Start a new alert session.

    Expected JSON body:
    {
        "destination_id": "uuid"
    }

    What happens:
    1. Stops any currently active alert (BR-01: one at a time)
    2. Creates a new AlertSession in the database
    3. Returns session info (frontend uses session_id to stop it later)
    """
    device = _get_device_from_cookie()
    if not device:
        return jsonify({'error': 'Device not identified'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    destination_id = data.get('destination_id')
    if not destination_id:
        return jsonify({'error': 'destination_id is required'}), 400

    # Verify destination belongs to this device
    destination = destination_service.get_destination(destination_id, device.id)
    if not destination:
        return jsonify({'error': 'Destination not found'}), 404

    # Start the alert (also stops any existing active alert)
    session = alert_service.start_alert(device.id, destination_id)

    return jsonify({
        'alert_session_id': session.id,
        'destination_name': destination.name,
        'threshold_minutes': destination.alert_threshold_minutes,
        'status': 'active'
    }), 201


@alert_bp.route('/alert/stop', methods=['POST'])
@limiter.limit("10 per minute")
def stop_alert():
    """
    Stop an active alert session.

    Expected JSON body:
    {
        "alert_session_id": "uuid",
        "reason": "user_stopped" | "alert_fired" | "error"
    }

    'reason' tells us WHY it stopped:
    - "user_stopped": User tapped "Stop Alert"
    - "alert_fired": The alert went off and user dismissed it
    - "error": Something went wrong (GPS died, network error, etc.)
    """
    device = _get_device_from_cookie()
    if not device:
        return jsonify({'error': 'Device not identified'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    session_id = data.get('alert_session_id')
    reason = data.get('reason', 'user_stopped')

    if not session_id:
        return jsonify({'error': 'alert_session_id is required'}), 400

    # Validate reason
    valid_reasons = ['user_stopped', 'alert_fired', 'error']
    if reason not in valid_reasons:
        return jsonify({'error': f'reason must be one of: {valid_reasons}'}), 400

    session = alert_service.stop_alert(session_id, device.id, reason)

    if not session:
        return jsonify({'error': 'Alert session not found'}), 404

    return jsonify({
        'alert_session_id': session.id,
        'status': 'stopped',
        'reason': reason,
        'alert_fired': session.alert_fired
    }), 200


@alert_bp.route('/alert/active', methods=['GET'])
@limiter.limit("30 per minute")
def get_active_alert():
    """
    Check if there's a currently active alert for this device.

    Used when the page reloads — the frontend checks if an alert
    was already running so it can resume polling.
    """
    device = _get_device_from_cookie()
    if not device:
        return jsonify({'error': 'Device not identified'}), 401

    active = alert_service.get_active_alert(device.id)

    if not active:
        return jsonify({'active': False}), 200

    # Get destination details for the active alert
    destination = destination_service.get_destination(
        active.destination_id, device.id
    )

    return jsonify({
        'active': True,
        'alert_session_id': active.id,
        'destination_id': active.destination_id,
        'destination_name': destination.name if destination else 'Unknown',
        'threshold_minutes': destination.alert_threshold_minutes if destination else 10,
        'started_at': active.started_at.isoformat() if active.started_at else None
    }), 200


def _get_device_from_cookie():
    """Helper to extract device from cookie."""
    cookie_token = request.cookies.get('pingplace_device')
    if not cookie_token:
        return None
    return device_service.get_or_create_device(cookie_token)
