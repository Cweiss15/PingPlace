"""
tests/test_subway_service.py — Tests for the NYC Subway Routing Service

Follows the same pattern as test_eta_service.py:
  - No real network calls
  - Uses the `app` fixture from conftest.py for Flask app context
  - Tests both happy paths and edge/error cases
"""

import math
import pytest
from services.subway_service import (
    calculate_subway_eta,
    _haversine_km,
    _walk_minutes,
    _nearest_stations,
    STATIONS,
    TRANSFER_PENALTY_MIN,
    WALKING_SPEED_KMH,
    MAX_WALK_KM,
)


# ---------------------------------------------------------------------------
# Unit tests — pure helpers (no app context needed)
# ---------------------------------------------------------------------------

class TestHaversine:
    def test_same_point_is_zero(self):
        assert _haversine_km(40.7128, -74.006, 40.7128, -74.006) == pytest.approx(0.0, abs=1e-9)

    def test_known_distance(self):
        # Times Sq to Grand Central is roughly 1.0 km
        dist = _haversine_km(40.7549, -73.9874, 40.7527, -73.9772)
        assert 0.5 < dist < 1.5

    def test_symmetry(self):
        d1 = _haversine_km(40.71, -74.00, 40.75, -73.98)
        d2 = _haversine_km(40.75, -73.98, 40.71, -74.00)
        assert d1 == pytest.approx(d2, abs=1e-9)


class TestWalkMinutes:
    def test_one_km_at_standard_speed(self):
        expected = (1.0 / WALKING_SPEED_KMH) * 60.0
        assert _walk_minutes(1.0) == pytest.approx(expected)

    def test_zero_distance(self):
        assert _walk_minutes(0.0) == 0.0


class TestNearestStations:
    def test_times_square_coords_returns_candidates(self):
        # Coordinates right at Times Square should find nearby stations
        results = _nearest_stations(40.7549, -73.9874)
        assert len(results) > 0
        ids = [s for s, _ in results]
        assert "times_sq_1" in ids

    def test_walk_minutes_are_sorted_ascending(self):
        results = _nearest_stations(40.7549, -73.9874)
        mins = [w for _, w in results]
        assert mins == sorted(mins)

    def test_far_away_coords_return_empty(self):
        # Middle of the Atlantic Ocean — no stations within MAX_WALK_KM
        results = _nearest_stations(30.0, -40.0)
        assert results == []

    def test_respects_max_walk_km(self):
        results = _nearest_stations(40.7549, -73.9874)
        for sid, walk_min in results:
            s = STATIONS[sid]
            km = _haversine_km(40.7549, -73.9874, s.lat, s.lng)
            assert km <= MAX_WALK_KM


# ---------------------------------------------------------------------------
# Integration tests — full routing (no network calls needed; graph is local)
# ---------------------------------------------------------------------------

class TestCalculateSubwayEta:
    """
    Full routing tests. Because the station graph is entirely in-memory,
    no mocking is required. The `app` fixture is still accepted so these
    tests run inside a Flask app context if needed by future expansions.
    """

    def test_manhattan_to_brooklyn_returns_ok(self, app):
        """Times Square → Atlantic Av–Barclays Ctr should find a route."""
        with app.app_context():
            result = calculate_subway_eta(
                origin_lat=40.7549, origin_lng=-73.9874,   # near Times Sq
                dest_lat=40.6840,   dest_lng=-73.9770,     # near Atlantic Av
            )
        assert result['status'] == 'OK'
        assert isinstance(result['minutes'], int)
        assert result['minutes'] > 0
        assert isinstance(result['route'], list)
        assert len(result['route']) >= 2  # at least walk-in and walk-out steps

    def test_response_keys_are_complete(self, app):
        with app.app_context():
            result = calculate_subway_eta(
                origin_lat=40.7549, origin_lng=-73.9874,
                dest_lat=40.6840,   dest_lng=-73.9770,
            )
        for key in ('minutes', 'walkingMinutes', 'trainMinutes', 'transfers', 'route', 'status'):
            assert key in result, f"Missing key: {key}"

    def test_minutes_equals_walking_plus_train(self, app):
        with app.app_context():
            result = calculate_subway_eta(
                origin_lat=40.7549, origin_lng=-73.9874,
                dest_lat=40.6840,   dest_lng=-73.9770,
            )
        if result['status'] == 'OK':
            # Total should be roughly walkingMinutes + trainMinutes + transfer penalties
            assert result['minutes'] >= result['walkingMinutes'] + result['trainMinutes']

    def test_no_route_when_origin_far_from_subway(self, app):
        """Coordinates far from any subway station should return NO_ROUTE."""
        with app.app_context():
            result = calculate_subway_eta(
                origin_lat=40.9000, origin_lng=-74.5000,   # far from Manhattan
                dest_lat=40.6840,   dest_lng=-73.9770,
            )
        assert result['status'] == 'NO_ROUTE'
        assert result['minutes'] is None
        assert 'error' in result

    def test_no_route_when_destination_far_from_subway(self, app):
        with app.app_context():
            result = calculate_subway_eta(
                origin_lat=40.7549, origin_lng=-73.9874,
                dest_lat=41.5000,   dest_lng=-74.5000,     # far from Brooklyn
            )
        assert result['status'] == 'NO_ROUTE'

    def test_walking_minutes_are_non_negative(self, app):
        with app.app_context():
            result = calculate_subway_eta(
                origin_lat=40.7549, origin_lng=-73.9874,
                dest_lat=40.6840,   dest_lng=-73.9770,
            )
        if result['status'] == 'OK':
            assert result['walkingMinutes'] >= 0
            assert result['trainMinutes'] >= 0

    def test_transfer_count_is_non_negative_int(self, app):
        with app.app_context():
            result = calculate_subway_eta(
                origin_lat=40.7549, origin_lng=-73.9874,
                dest_lat=40.6840,   dest_lng=-73.9770,
            )
        if result['status'] == 'OK':
            assert isinstance(result['transfers'], int)
            assert result['transfers'] >= 0

    def test_14th_street_l_to_bedford_is_short(self, app):
        """14 St (Union Sq area) to Bedford Av on the L should be ~10 min."""
        with app.app_context():
            result = calculate_subway_eta(
                origin_lat=40.7352, origin_lng=-73.9902,   # 14 St–Union Sq
                dest_lat=40.7171,   dest_lng=-73.9563,     # Bedford Av
            )
        if result['status'] == 'OK':
            # Should be under 25 minutes total (it's one stop + a short walk)
            assert result['minutes'] < 25
