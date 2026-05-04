"""
tests/test_eta_service.py — Tests for ETA Calculation Service

Tests the eta_service which calls Google Distance Matrix API.
We use "mocking" to fake the API response — we don't want tests to:
1. Make real API calls (costs money, needs internet)
2. Depend on traffic conditions (non-deterministic)

WHAT IS MOCKING?
Mocking replaces a real function with a fake one that returns whatever
we tell it to. This isolates our code from external dependencies.

unittest.mock.patch temporarily replaces a function during the test,
then restores it automatically when the test finishes.
"""

from unittest.mock import patch, MagicMock
from services.eta_service import calculate_eta


class TestCalculateEta:
    """Tests for the calculate_eta function."""

    @patch('services.eta_service.requests.get')
    def test_successful_eta_calculation(self, mock_get, app):
        """Should return ETA when Google API returns valid data."""
        # Arrange: Set up fake API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'OK',
            'rows': [{
                'elements': [{
                    'status': 'OK',
                    'duration_in_traffic': {
                        'value': 1800,  # 1800 seconds = 30 minutes
                        'text': '30 mins'
                    },
                    'distance': {
                        'value': 25000,
                        'text': '25 km'
                    }
                }]
            }]
        }
        mock_get.return_value = mock_response

        with app.app_context():
            # Act
            result = calculate_eta(40.7128, -74.0060, 40.7580, -73.9855)

        # Assert
        assert result['status'] == 'OK'
        assert result['eta_minutes'] == 30
        assert result['eta_text'] == '30 mins'
        assert result['distance_text'] == '25 km'

    @patch('services.eta_service.requests.get')
    def test_no_route_found(self, mock_get, app):
        """Should handle 'no route' response gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'OK',
            'rows': [{
                'elements': [{
                    'status': 'ZERO_RESULTS'
                }]
            }]
        }
        mock_get.return_value = mock_response

        with app.app_context():
            result = calculate_eta(40.7128, -74.0060, 35.6762, 139.6503)

        assert result['status'] == 'NO_ROUTE'
        assert result['eta_minutes'] is None

    @patch('services.eta_service.requests.get')
    def test_api_error_handling(self, mock_get, app):
        """Should handle API errors without crashing."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        with app.app_context():
            result = calculate_eta(40.7128, -74.0060, 40.7580, -73.9855)

        assert result['status'] == 'ERROR'
        assert result['eta_minutes'] is None

    @patch('services.eta_service.requests.get')
    def test_network_timeout(self, mock_get, app):
        """Should handle network timeouts gracefully."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout('Connection timed out')

        with app.app_context():
            result = calculate_eta(40.7128, -74.0060, 40.7580, -73.9855)

        assert result['status'] == 'ERROR'
        assert result['eta_minutes'] is None
