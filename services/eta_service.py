"""
services/eta_service.py — ETA Service

The core of PingPlace — calculates how long it will take to reach
a destination, accounting for current traffic conditions.

This service:
1. Receives the user's current GPS coordinates
2. Calls Google Maps Distance Matrix API
3. Returns the estimated travel time WITH traffic

The Distance Matrix API is different from the Directions API:
- Directions API: gives you turn-by-turn route instructions
- Distance Matrix API: just gives you time + distance (cheaper, faster)

We only need the time, so Distance Matrix is the right choice.
"""

import requests
from flask import current_app


def calculate_eta(origin_lat, origin_lng, dest_lat, dest_lng):
    """
    Calculate estimated travel time from origin to destination using Google
    Distance Matrix API with live traffic data.

    Args:
        origin_lat: User's current latitude (from phone GPS)
        origin_lng: User's current longitude
        dest_lat: Destination's latitude (from saved destination)
        dest_lng: Destination's longitude

    Returns:
        Dictionary with ETA info:
        {
            'eta_minutes': 12,          # Integer minutes
            'eta_text': '12 mins',      # Human-readable string from Google
            'distance_text': '5.2 km',  # Human-readable distance
            'status': 'OK'              # 'OK' or 'ERROR'
        }

    How the Google API call works:
        URL: https://maps.googleapis.com/maps/api/distancematrix/json
        Parameters:
            - origins: "lat,lng" of user's current position
            - destinations: "lat,lng" of where they're going
            - departure_time: "now" (tells Google to use live traffic)
            - traffic_model: "best_guess" (most accurate prediction)
            - key: your API key
    """
    api_key = current_app.config['GOOGLE_API_KEY']

    if not api_key:
        return {
            'eta_minutes': None,
            'eta_text': 'API key not configured',
            'distance_text': None,
            'status': 'ERROR',
            'error': 'Google API key is not set'
        }

    # Build the API request URL
    url = 'https://maps.googleapis.com/maps/api/distancematrix/json'
    params = {
        'origins': f'{origin_lat},{origin_lng}',
        'destinations': f'{dest_lat},{dest_lng}',
        'departure_time': 'now',         # Use current traffic conditions
        'traffic_model': 'best_guess',   # Google's best ETA prediction
        'key': api_key
    }

    try:
        # Make the HTTP request to Google (timeout after 10 seconds)
        response = requests.get(url, params=params, timeout=10)

        # Raise an exception if HTTP status is 4xx or 5xx
        response.raise_for_status()

        data = response.json()

        # Check if Google returned valid results
        if data.get('status') != 'OK':
            return {
                'eta_minutes': None,
                'eta_text': None,
                'distance_text': None,
                'status': 'ERROR',
                'error': f"API returned status: {data.get('status')}"
            }

        # Extract the result (first origin → first destination)
        element = data['rows'][0]['elements'][0]

        if element.get('status') != 'OK':
            return {
                'eta_minutes': None,
                'eta_text': None,
                'distance_text': None,
                'status': 'ERROR',
                'error': f"Route status: {element.get('status')}"
            }

        # Google returns 'duration_in_traffic' when departure_time is set
        # This is the traffic-aware ETA (the whole point of PingPlace!)
        # Falls back to regular 'duration' if traffic data isn't available
        duration_data = element.get('duration_in_traffic', element.get('duration', {}))

        # 'value' is seconds, 'text' is human-readable (e.g., "12 mins")
        eta_seconds = duration_data.get('value', 0)
        eta_text = duration_data.get('text', 'Unknown')
        eta_minutes = round(eta_seconds / 60)

        distance_text = element.get('distance', {}).get('text', 'Unknown')

        return {
            'eta_minutes': eta_minutes,
            'eta_text': eta_text,
            'distance_text': distance_text,
            'status': 'OK'
        }

    except requests.exceptions.Timeout:
        return {
            'eta_minutes': None,
            'eta_text': None,
            'distance_text': None,
            'status': 'ERROR',
            'error': 'Request timed out — Google API did not respond in 10 seconds'
        }
    except requests.exceptions.RequestException as e:
        # Catches all network errors (no internet, DNS failure, etc.)
        return {
            'eta_minutes': None,
            'eta_text': None,
            'distance_text': None,
            'status': 'ERROR',
            'error': f'Network error: {str(e)}'
        }
