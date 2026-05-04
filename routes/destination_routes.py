"""
routes/destination_routes.py — Destination API Routes

CRUD endpoints for managing saved destinations.

Endpoints:
    GET    /api/destinations         → List all destinations for this device
    POST   /api/destinations         → Add a new destination
    PUT    /api/destinations/<id>    → Update a destination
    DELETE /api/destinations/<id>    → Delete a destination
"""

from flask import Blueprint, request, jsonify
from services import destination_service, device_service
from app import limiter

destination_bp = Blueprint('destinations', __name__)


def get_device_from_cookie():
    """
    Helper: Extract device from the request cookie.
    Returns the device object or None.

    Used by all endpoints in this file — every request must come
    from an identified device (ownership verification).
    """
    cookie_token = request.cookies.get('pingplace_device')
    if not cookie_token:
        return None
    return device_service.get_or_create_device(cookie_token)


@destination_bp.route('/destinations', methods=['GET'])
@limiter.limit("30 per minute")
def list_destinations():
    """
    Get all saved destinations for the current device.

    Response: [
        { "id": "...", "name": "Home", "address": "...", ... },
        { "id": "...", "name": "Work", "address": "...", ... }
    ]
    """
    device = get_device_from_cookie()
    if not device:
        return jsonify({'error': 'Device not identified'}), 401

    destinations = destination_service.list_destinations(device.id)
    return jsonify([d.to_dict() for d in destinations]), 200


@destination_bp.route('/destinations', methods=['POST'])
@limiter.limit("10 per minute")
def create_destination():
    """
    Add a new saved destination.

    Expected JSON body:
    {
        "name": "Home",
        "address": "123 Main St, City, State",
        "place_id": "ChIJ...",      (from Google Places)
        "latitude": 40.7128,
        "longitude": -74.0060,
        "alert_threshold_minutes": 10   (optional, defaults to 10)
    }

    Validation rules (Business Rule BR-07):
    - name: required, max 50 chars
    - address: required
    - place_id: required
    - latitude: required, -90 to 90
    - longitude: required, -180 to 180
    - alert_threshold_minutes: 1 to 120, default 10
    """
    device = get_device_from_cookie()
    if not device:
        return jsonify({'error': 'Device not identified'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    # ---- Input Validation (SECURITY-05) ----
    name = data.get('name', '').strip()
    address = data.get('address', '').strip()
    place_id = data.get('place_id', '').strip()
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    threshold = data.get('alert_threshold_minutes', 10)

    # Validate required fields
    errors = []
    if not name:
        errors.append('name is required')
    elif len(name) > 50:
        errors.append('name must be 50 characters or less')

    if not address:
        errors.append('address is required')
    elif len(address) > 500:
        errors.append('address must be 500 characters or less')

    if not place_id:
        errors.append('place_id is required')
    elif len(place_id) > 300:
        errors.append('place_id must be 300 characters or less')

    if latitude is None:
        errors.append('latitude is required')
    elif not isinstance(latitude, (int, float)) or latitude < -90 or latitude > 90:
        errors.append('latitude must be a number between -90 and 90')

    if longitude is None:
        errors.append('longitude is required')
    elif not isinstance(longitude, (int, float)) or longitude < -180 or longitude > 180:
        errors.append('longitude must be a number between -180 and 180')

    if not isinstance(threshold, int) or threshold < 1 or threshold > 120:
        errors.append('alert_threshold_minutes must be an integer between 1 and 120')

    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    # ---- Create the destination ----
    destination = destination_service.create_destination(
        device_id=device.id,
        name=name,
        address=address,
        place_id=place_id,
        latitude=latitude,
        longitude=longitude,
        alert_threshold_minutes=threshold
    )

    return jsonify(destination.to_dict()), 201


@destination_bp.route('/destinations/<destination_id>', methods=['PUT'])
@limiter.limit("10 per minute")
def update_destination(destination_id):
    """
    Update a destination's name or threshold.

    URL parameter:
        destination_id — UUID of the destination to update

    Expected JSON body (all fields optional):
    {
        "name": "New Name",
        "alert_threshold_minutes": 15
    }
    """
    device = get_device_from_cookie()
    if not device:
        return jsonify({'error': 'Device not identified'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    # Validate update fields
    kwargs = {}

    if 'name' in data:
        name = data['name'].strip() if isinstance(data['name'], str) else ''
        if not name or len(name) > 50:
            return jsonify({'error': 'name must be 1-50 characters'}), 400
        kwargs['name'] = name

    if 'alert_threshold_minutes' in data:
        threshold = data['alert_threshold_minutes']
        if not isinstance(threshold, int) or threshold < 1 or threshold > 120:
            return jsonify({'error': 'alert_threshold_minutes must be 1-120'}), 400
        kwargs['alert_threshold_minutes'] = threshold

    if not kwargs:
        return jsonify({'error': 'No valid fields to update'}), 400

    destination = destination_service.update_destination(
        destination_id=destination_id,
        device_id=device.id,
        **kwargs
    )

    if not destination:
        return jsonify({'error': 'Destination not found'}), 404

    return jsonify(destination.to_dict()), 200


@destination_bp.route('/destinations/<destination_id>', methods=['DELETE'])
@limiter.limit("10 per minute")
def delete_destination(destination_id):
    """
    Delete a saved destination.

    URL parameter:
        destination_id — UUID of the destination to delete
    """
    device = get_device_from_cookie()
    if not device:
        return jsonify({'error': 'Device not identified'}), 401

    success = destination_service.delete_destination(destination_id, device.id)

    if not success:
        return jsonify({'error': 'Destination not found'}), 404

    return jsonify({'message': 'Destination deleted'}), 200
