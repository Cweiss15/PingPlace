"""
routes/device_routes.py — Device API Routes

Handles user identification via browser cookies.

Endpoints:
    POST /api/device  → Create or retrieve a device (called on page load)
"""

from flask import Blueprint, request, jsonify, make_response
from services import device_service
from app import limiter

device_bp = Blueprint('device', __name__)


@device_bp.route('/device', methods=['POST'])
@limiter.limit("10 per minute")  # Prevent abuse
def create_or_get_device():
    """
    Create a new device or retrieve existing one based on cookie.

    How it works:
    1. Frontend sends a POST request when page loads
    2. We check if the request has our 'pingplace_device' cookie
    3. If yes → find that device in the database, return its data
    4. If no → create a new device, set the cookie in the response

    The cookie is set as:
    - httponly=True: JavaScript can't read it (prevents XSS attacks from stealing it)
    - secure=True: Only sent over HTTPS
    - samesite='Lax': Only sent with same-site requests (CSRF protection)
    - max_age=365 days: Persists for a year
    """
    # Try to get existing cookie from the request
    cookie_token = request.cookies.get('pingplace_device')

    # Get or create the device
    device = device_service.get_or_create_device(cookie_token)

    # Build the JSON response
    response = make_response(jsonify({
        'device_id': device.id,
        'is_new': cookie_token is None  # True if this is a first-time visitor
    }))

    # Set the cookie in the response (browser will store it)
    response.set_cookie(
        'pingplace_device',          # Cookie name
        device.cookie_token,         # Cookie value (the UUID)
        max_age=365 * 24 * 60 * 60,  # Expires in 1 year (seconds)
        httponly=True,                # Can't be read by JavaScript
        secure=True,                 # Only sent over HTTPS
        samesite='Lax'               # CSRF protection
    )

    return response, 200
