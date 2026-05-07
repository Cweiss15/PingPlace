"""
routes/eta_routes.py — ETA Calculation Route

The most important endpoint in the app:
Frontend sends GPS coordinates → Server calculates ETA with traffic → Returns minutes.

Endpoint:
    POST /api/eta → Calculate travel time from current position to destination
"""

import os
import requests
from flask import Blueprint, request, jsonify
from services import eta_service, destination_service, device_service
from extensions import limiter

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
eta_bp = Blueprint('eta', __name__)


def get_eta_from_google(origin_lat, origin_lng, dest_lat, dest_lng):
    """
    Call Google Distance Matrix API to get the ETA.
    Returns (eta_minutes, eta_text) or (None, None) on failure.
    """
    if not GOOGLE_API_KEY:
        print("Warning: GOOGLE_API_KEY not set")
        return None, None

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": f"{origin_lat},{origin_lng}",
        "destinations": f"{dest_lat},{dest_lng}",
        "key": GOOGLE_API_KEY,
        "mode": "driving",
        "departure_time": "now"  # get traffic-aware ETA
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        if data.get("status") == "OK":
            element = data["rows"][0]["elements"][0]
            if element.get("status") == "OK":
                # Prefer duration_in_traffic if available
                duration_sec = element.get("duration_in_traffic", element.get("duration"))["value"]
                eta_minutes = int(duration_sec / 60)
                eta_text = element.get("duration_in_traffic", element.get("duration"))["text"]
                return eta_minutes, eta_text
            else:
                print(f"Distance Matrix element status: {element.get('status')}")
        else:
            print(f"Distance Matrix API error: {data.get('status')} - {data.get('error_message', '')}")
            if data.get("status") == "REQUEST_DENIED":
                return get_eta_from_osrm(origin_lat, origin_lng, dest_lat, dest_lng)

    except Exception as e:
        print(f"Error fetching ETA from Google: {e}")

    return None, None


def get_eta_from_osrm(origin_lat, origin_lng, dest_lat, dest_lng):
    """
    Fallback: Open Source Routing Machine (OSRM).
    Used if Google Distance Matrix API is disabled/denied.
    Note: OSRM uses longitude,latitude order!
    """
    print("Using OSRM fallback for ETA...")
    url = f"http://router.project-osrm.org/route/v1/driving/{origin_lng},{origin_lat};{dest_lng},{dest_lat}?overview=false"
    
    try:
        # Add a custom user-agent as required by OSRM terms of use
        headers = {'User-Agent': 'PingPlace-Commuter-App/1.0'}
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        
        if data.get("code") == "Ok":
            duration_sec = data["routes"][0]["duration"]
            eta_minutes = int(duration_sec / 60)
            eta_text = f"{eta_minutes} mins"
            return eta_minutes, eta_text
        else:
            print(f"OSRM error: {data.get('code')}")
    except Exception as e:
        print(f"Error fetching ETA from OSRM: {e}")
        
    return None, None


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
    4. Calls eta_service.calculate_eta() which hits Google Distance Matrix
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

    if latitude is None or longitude is None:
        return jsonify({'error': 'latitude and longitude are required'}), 400

    if not isinstance(latitude, (int, float)) or latitude < -90 or latitude > 90:
        return jsonify({'error': 'latitude must be between -90 and 90'}), 400

    if not isinstance(longitude, (int, float)) or longitude < -180 or longitude > 180:
        return jsonify({'error': 'longitude must be between -180 and 180'}), 400

    if not destination_id:
        return jsonify({'error': 'destination_id is required'}), 400

    # ---- Verify destination belongs to this device (IDOR prevention) ----
    destination = destination_service.get_destination(destination_id, device.id)
    if not destination:
        return jsonify({'error': 'Destination not found'}), 404

    # ---- Calculate ETA via Google Distance Matrix API ----
    result = eta_service.calculate_eta(
        origin_lat=latitude,
        origin_lng=longitude,
        dest_lat=destination.latitude,
        dest_lng=destination.longitude
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
