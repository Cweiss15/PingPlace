"""
services/eta_service.py — ETA Service

Calculates travel time from the user's current location to a destination.

Travel mode logic:
  - car   → TomTom (traffic-aware)
  - bus   → TomTom (traffic-aware)
  - train → 1. TomTom car time × 1.15  (walk + wait overhead)
             2. Dijkstra subway graph    (NYC offline graph)
             3. OSRM × 1.15             (last resort)
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
# OSRM fallback (last resort, no API key needed)
# ──────────────────────────────────────────────────────────────────────────────

def _get_eta_from_osrm(origin_lat, origin_lng, dest_lat, dest_lng):
    """
    Open Source Routing Machine — free, no API key, no real-time traffic.
    Last-resort fallback for train mode when both Google Transit and the
    local subway graph fail.

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


# Transit overhead: subway is ~15% longer than car (walk to station + wait time).
# Used when real transit data isn’t available so estimates stay comparable to car/bus.
_TRANSIT_OVERHEAD = 1.15


def _estimate_transit_from_tomtom(origin_lat, origin_lng, dest_lat, dest_lng):
    """
    Derive a transit estimate from TomTom’s car time.

    TomTom already works for car/bus, so this always produces a reasonable
    train number when Google Directions transit is unavailable.
    Adds _TRANSIT_OVERHEAD to account for walking to the station and
    waiting on the platform.

    Returns:
        (eta_minutes, eta_text) or (None, None) on failure
    """
    car_min, _, _ = _get_eta_from_tomtom(origin_lat, origin_lng, dest_lat, dest_lng, 'car')
    if car_min is None:
        return None, None
    est = round(car_min * _TRANSIT_OVERHEAD)
    return est, f"{est} min (transit estimate)"





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
            'eta_minutes':   int | None,
            'eta_text':      str | None,
            'traffic_delay': int | None,   # always 0 for train
            'travel_mode':   str,
            'status':        'OK' | 'ERROR',
            'error':         str           # only present on ERROR
            # train mode also includes:
            'walkingMinutes': int,
            'trainMinutes':   int,
            'transfers':      int,
            'route':          list[str],
            'provider':       str          # which data source answered
        }
    """
    eta_minutes = eta_text = traffic_delay = None
    route_details: dict | None = None
    provider = None

    if travel_mode in ('car', 'bus'):
        # ── Car / Bus: TomTom (traffic-aware) ───────────────────────────────
        eta_minutes, eta_text, traffic_delay = _get_eta_from_tomtom(
            origin_lat, origin_lng, dest_lat, dest_lng, travel_mode
        )
        if eta_minutes is None:
            print("TomTom failed — falling back to OSRM")
            eta_minutes, eta_text, traffic_delay = _get_eta_from_osrm(
                origin_lat, origin_lng, dest_lat, dest_lng
            )

    else:
        # ── Train: three-provider chain, first success wins ──────────────────
        traffic_delay = 0   # trains run on schedules, not traffic

        # 1. TomTom car time × overhead — reliable since TomTom already works
        eta_minutes, eta_text = _estimate_transit_from_tomtom(
            origin_lat, origin_lng, dest_lat, dest_lng
        )
        if eta_minutes is not None:
            provider = 'tomtom_estimate'

        # 3. Local Dijkstra subway graph — offline, NYC coverage, no API key
        if eta_minutes is None:
            print("TomTom estimate failed — trying subway graph …")
            from services.subway_service import calculate_subway_eta
            subway = calculate_subway_eta(origin_lat, origin_lng, dest_lat, dest_lng)
            if subway['status'] == 'OK':
                eta_minutes  = subway['minutes']
                eta_text     = f"{eta_minutes} min (subway estimate)"
                route_details = {
                    'walkingMinutes': subway['walkingMinutes'],
                    'trainMinutes':   subway['trainMinutes'],
                    'transfers':      subway['transfers'],
                    'route':          subway['route'],
                }
                provider = 'subway_graph'

        # 4. OSRM × overhead — last resort
        if eta_minutes is None:
            print("All transit providers failed — falling back to OSRM …")
            osrm_min, _, _ = _get_eta_from_osrm(origin_lat, origin_lng, dest_lat, dest_lng)
            if osrm_min is not None:
                eta_minutes = round(osrm_min * _TRANSIT_OVERHEAD)
                eta_text    = f"{eta_minutes} min (estimated)"
                provider    = 'osrm'

    if eta_minutes is None:
        return {
            'eta_minutes':   None,
            'eta_text':      None,
            'traffic_delay': None,
            'travel_mode':   travel_mode,
            'status':        'ERROR',
            'error':         'Could not calculate ETA — all providers failed',
        }

    result = {
        'eta_minutes':   eta_minutes,
        'eta_text':      eta_text,
        'traffic_delay': traffic_delay,
        'travel_mode':   travel_mode,
        'status':        'OK',
    }

    # Attach enriched transit breakdown when available (train mode only)
    if route_details:
        result.update(route_details)
        result['provider'] = provider

    return result
