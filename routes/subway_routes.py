"""
routes/subway_routes.py — NYC Subway ETA Route

Endpoint:
    POST /api/subway-eta
        Accepts origin + destination coordinates and returns a detailed
        subway travel estimate with walking legs and transfer penalties.
"""

from flask import Blueprint, request, jsonify
from services import subway_service
from extensions import limiter

subway_bp = Blueprint('subway', __name__)


@subway_bp.route('/subway-eta', methods=['POST'])
@limiter.limit("20 per minute")
def subway_eta():
    """
    Calculate estimated subway travel time between two coordinates.

    Request JSON:
    {
        "origin_lat":  40.7128,
        "origin_lng": -74.0060,
        "dest_lat":    40.6892,
        "dest_lng":   -73.9442
    }

    Response (success):
    {
        "minutes": 42,
        "walkingMinutes": 8,
        "trainMinutes": 30,
        "transfers": 1,
        "route": ["Walk 4 min to Times Sq–42 St", ...],
        "status": "OK"
    }

    Response (error):
    {
        "status": "NO_ROUTE" | "ERROR",
        "error": "description"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    origin_lat = data.get('origin_lat')
    origin_lng = data.get('origin_lng')
    dest_lat   = data.get('dest_lat')
    dest_lng   = data.get('dest_lng')

    errors = []
    for val, lo, hi, name in [
        (origin_lat, -90,  90,  'origin_lat'),
        (origin_lng, -180, 180, 'origin_lng'),
        (dest_lat,   -90,  90,  'dest_lat'),
        (dest_lng,   -180, 180, 'dest_lng'),
    ]:
        if val is None:
            errors.append(f"{name} is required")
        elif not isinstance(val, (int, float)) or not (lo <= val <= hi):
            errors.append(f"{name} must be a number between {lo} and {hi}")

    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    result = subway_service.calculate_subway_eta(
        origin_lat=float(origin_lat),
        origin_lng=float(origin_lng),
        dest_lat=float(dest_lat),
        dest_lng=float(dest_lng),
    )

    status_code = 200 if result['status'] == 'OK' else 404
    return jsonify(result), status_code
