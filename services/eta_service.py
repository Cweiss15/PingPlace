"""
services/eta_service.py — ETA Service

Calculates travel time from the user's current location to a destination.

Travel mode logic:
  - car  → TomTom Routing API  (travelMode=car,  traffic-aware)
  - bus  → TomTom Routing API  (travelMode=bus,  traffic-aware)
  - train→ OSRM public routing (no real-time traffic; trains run on schedules)

TomTom is the primary provider for car/bus because it:
  1. Has a generous free tier (2 500 free routing calls/day)
  2. Returns live traffic-delay data via `trafficDelayInSeconds`
  3. Supports a `travelMode` parameter so we can distinguish car vs bus
"""

import requests
from flask import current_app


# ──────────────────────────────────────────────────────────────────────────────
# TomTom Routing API
# ──────────────────────────────────────────────────────────────────────────────

def _get_eta_from_tomtom(origin_lat, origin_lng, dest_lat, dest_lng, travel_mode='car'):
    """
    Call TomTom Calculate Route API with live traffic.

    TomTom URL pattern:
        /routing/1/calculateRoute/{origin_lat},{origin_lng}:{dest_lat},{dest_lng}/json
            ?key=...
            &travelMode=car|bus
            &traffic=true
            &computeTravelTimeFor=all   ← returns both with- and without-traffic times

    Args:
        travel_mode: 'car' or 'bus'  (TomTom beta supports 'bus')

    Returns:
        (eta_minutes, eta_text, traffic_delay_minutes) or (None, None, None) on failure
    """
    api_key = current_app.config.get('TOMTOM_API_KEY', '')
    if not api_key:
        print("Warning: TOMTOM_API_KEY not configured")
        return None, None, None

    # Normalise mode — TomTom uses lowercase 'car' or 'bus'
    tt_mode = 'bus' if travel_mode == 'bus' else 'car'

    url = (
        f"https://api.tomtom.com/routing/1/calculateRoute/"
        f"{origin_lat},{origin_lng}:{dest_lat},{dest_lng}/json"
    )
    params = {
        'key': api_key,
        'travelMode': tt_mode,
        'traffic': 'true',
        'computeTravelTimeFor': 'all',   # includes noTrafficTravelTimeInSeconds
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        routes = data.get('routes', [])
        if not routes:
            print(f"TomTom: no routes in response — {data}")
            return None, None, None

        summary = routes[0].get('summary', {})

        # travelTimeInSeconds already includes traffic delay
        travel_sec = summary.get('travelTimeInSeconds', 0)
        no_traffic_sec = summary.get('noTrafficTravelTimeInSeconds', travel_sec)
        delay_sec = max(0, travel_sec - no_traffic_sec)

        eta_minutes = round(travel_sec / 60)
        delay_minutes = round(delay_sec / 60)
        eta_text = f"{eta_minutes} min"
        if delay_minutes > 0:
            eta_text += f" (+{delay_minutes} min traffic)"

        return eta_minutes, eta_text, delay_minutes

    except requests.exceptions.Timeout:
        print("TomTom API timed out")
        return None, None, None
    except Exception as e:
        print(f"TomTom API error: {e}")
        return None, None, None


# ──────────────────────────────────────────────────────────────────────────────
# OSRM fallback (train / no-traffic baseline)
# ──────────────────────────────────────────────────────────────────────────────

def _get_eta_from_osrm(origin_lat, origin_lng, dest_lat, dest_lng):
    """
    Open Source Routing Machine — free, no API key, no real-time traffic.
    Used for 'train' mode (schedules matter more than road traffic) and as a
    fallback when TomTom fails.

    Note: OSRM expects coordinates as  longitude,latitude  (not lat,lng)!
    """
    print("Using OSRM for ETA …")
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
        f"?overview=false"
    )
    headers = {'User-Agent': 'PingPlace-Commuter-App/1.0'}

    try:
        resp = requests.get(url, headers=headers, timeout=8)
        data = resp.json()
        if data.get('code') == 'Ok':
            duration_sec = data['routes'][0]['duration']
            eta_minutes = round(duration_sec / 60)
            return eta_minutes, f"{eta_minutes} min", 0
        else:
            print(f"OSRM error: {data.get('code')}")
    except Exception as e:
        print(f"OSRM error: {e}")

    return None, None, None


# ──────────────────────────────────────────────────────────────────────────────
# Public API used by eta_routes.py
# ──────────────────────────────────────────────────────────────────────────────

def calculate_eta(origin_lat, origin_lng, dest_lat, dest_lng, travel_mode='car'):
    """
    Calculate estimated travel time from origin to destination.

    Args:
        origin_lat / origin_lng : user's current GPS coordinates
        dest_lat   / dest_lng   : saved destination coordinates
        travel_mode             : 'car' | 'bus' | 'train'

    Returns:
        {
            'eta_minutes':     int | None,
            'eta_text':        str | None,   # e.g. "14 min (+3 min traffic)"
            'traffic_delay':   int | None,   # extra minutes due to traffic
            'travel_mode':     str,
            'status':          'OK' | 'ERROR',
            'error':           str           # only present on ERROR
        }
    """
    eta_minutes = eta_text = traffic_delay = None

    if travel_mode in ('car', 'bus'):
        # Primary: TomTom (traffic-aware)
        eta_minutes, eta_text, traffic_delay = _get_eta_from_tomtom(
            origin_lat, origin_lng, dest_lat, dest_lng, travel_mode
        )
        if eta_minutes is None:
            # Fallback to OSRM if TomTom fails
            print("TomTom failed — falling back to OSRM")
            eta_minutes, eta_text, traffic_delay = _get_eta_from_osrm(
                origin_lat, origin_lng, dest_lat, dest_lng
            )
    else:
        # 'train' — use OSRM (road-distance heuristic; trains ignore traffic)
        eta_minutes, eta_text, traffic_delay = _get_eta_from_osrm(
            origin_lat, origin_lng, dest_lat, dest_lng
        )

    if eta_minutes is None:
        return {
            'eta_minutes': None,
            'eta_text': None,
            'traffic_delay': None,
            'travel_mode': travel_mode,
            'status': 'ERROR',
            'error': 'Could not calculate ETA — all providers failed'
        }

    return {
        'eta_minutes':   eta_minutes,
        'eta_text':      eta_text,
        'traffic_delay': traffic_delay,
        'travel_mode':   travel_mode,
        'status':        'OK'
    }
