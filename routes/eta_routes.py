"""
routes/eta_routes.py — ETA Calculation Route

The most important endpoint in the app:
Frontend sends GPS coordinates → Server calculates ETA with traffic → Returns minutes.

Endpoint:
    POST /api/eta → Calculate travel time from current position to destination
"""

from flask import Blueprint, request, jsonify
from services import eta_service, destination_service, device_service
from extensions import limiter

eta_bp = Blueprint('eta', __name__)


@eta_bp.route('/eta', methods=['POST'])
@limiter.limit("30 per minute")  # Each poll cycle calls this once
def calculate_eta():
    """
    Calculate ETA from user's current location to a saved destination.

    Expected JSON body:
    {
        "latitude": 40.7128,       (user's current GPS lat)
        "longitude": -74.0060,     (user's current GPS lng)
        "destination_id": "uuid"   (which destination to calculate to)
    }

    Response (success):
    {
        "eta_minutes": 12,
        "eta_text": "12 mins",
        "distance_text": "5.2 km",
        "status": "OK"
    }

    Response (error):
    {
        "status": "ERROR",
        "error": "description of what went wrong"
    }

    How a single poll cycle uses this:
    1. Frontend JS gets GPS from phone → { lat: 40.71, lng: -74.00 }
    2. Frontend sends POST /api/eta with lat, lng, and destination_id
    3. This route validates the input
    4. Calls eta_service.calculate_eta() which uses TomTom (car/bus) or OSRM (train)
    5. Returns the ETA to the frontend
    6. Frontend checks: ETA <= threshold? If yes → fire alert
    """
    device = _get_device_from_cookie()
    if not device:
        return jsonify({'error': 'Device not identified'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    # ---- Input Validation ----
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    destination_id = data.get('destination_id')
    travel_mode = data.get('travel_mode', 'car')  # 'car' | 'bus' | 'train'

    if latitude is None or longitude is None:
        return jsonify({'error': 'latitude and longitude are required'}), 400

    if not isinstance(latitude, (int, float)) or latitude < -90 or latitude > 90:
        return jsonify({'error': 'latitude must be between -90 and 90'}), 400

    if not isinstance(longitude, (int, float)) or longitude < -180 or longitude > 180:
        return jsonify({'error': 'longitude must be between -180 and 180'}), 400

    if not destination_id:
        return jsonify({'error': 'destination_id is required'}), 400

    if travel_mode not in ('car', 'bus', 'train'):
        return jsonify({'error': 'travel_mode must be car, bus, or train'}), 400

    # ---- Verify destination belongs to this device (IDOR prevention) ----
    destination = destination_service.get_destination(destination_id, device.id)
    if not destination:
        return jsonify({'error': 'Destination not found'}), 404

    # ---- Calculate ETA via TomTom (car/bus) or OSRM (train) ----
    result = eta_service.calculate_eta(
        origin_lat=latitude,
        origin_lng=longitude,
        dest_lat=destination.latitude,
        dest_lng=destination.longitude,
        travel_mode=travel_mode
    )

    # Add destination context to the response
    result['destination_name'] = destination.name
    result['threshold_minutes'] = destination.alert_threshold_minutes

    if result['status'] == 'OK' and result['eta_minutes'] is not None:
        # Tell the frontend if it should fire the alert
        result['should_alert'] = result['eta_minutes'] <= destination.alert_threshold_minutes
    else:
        result['should_alert'] = False

    return jsonify(result), 200


def _get_device_from_cookie():
    """Helper to extract device from cookie. Returns None if not found."""
    cookie_token = request.cookies.get('pingplace_device')
    if not cookie_token:
        return None
    return device_service.get_device_by_cookie(cookie_token)
