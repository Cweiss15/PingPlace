"""
tests/test_routes.py — Integration Tests for API Routes

These test the full request/response cycle:
- HTTP request comes in
- Route handler processes it
- Database operations happen
- JSON response goes back

This tests that all the pieces (routes + services + models) work together.
Integration tests are different from unit tests:
- Unit tests: test ONE function in isolation (mock everything else)
- Integration tests: test the full flow (real DB, real service calls)
"""

import json


class TestDeviceRoutes:
    """Test the /api/device endpoint."""

    def test_register_device_creates_cookie(self, client):
        """POST /api/device should create a device and set a cookie."""
        response = client.post('/api/device')

        assert response.status_code == 200
        data = response.get_json()
        assert 'device_id' in data
        # Check that a cookie was set
        assert 'device_token' in response.headers.get('Set-Cookie', '')

    def test_register_device_returns_same_device(self, client):
        """Second call with same cookie should return same device."""
        # First call (creates device)
        response1 = client.post('/api/device')
        device_id_1 = response1.get_json()['device_id']

        # Second call (should return same device due to cookie)
        response2 = client.post('/api/device')
        device_id_2 = response2.get_json()['device_id']

        assert device_id_1 == device_id_2


class TestDestinationRoutes:
    """Test the /api/destinations endpoints."""

    def _register_device(self, client):
        """Helper: register a device first (needed for all destination tests)."""
        client.post('/api/device')

    def test_create_destination(self, client):
        """POST /api/destinations should create a new destination."""
        self._register_device(client)

        response = client.post('/api/destinations',
            data=json.dumps({
                'name': 'Home',
                'address': '123 Main St',
                'place_id': 'ChIJ_test123',
                'latitude': 40.7128,
                'longitude': -74.0060,
                'alert_threshold_minutes': 15
            }),
            content_type='application/json'
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data['name'] == 'Home'
        assert data['alert_threshold_minutes'] == 15

    def test_create_destination_validates_name_length(self, client):
        """Should reject names longer than 50 characters."""
        self._register_device(client)

        response = client.post('/api/destinations',
            data=json.dumps({
                'name': 'A' * 51,  # 51 characters — too long!
                'latitude': 40.7128,
                'longitude': -74.0060
            }),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_create_destination_validates_latitude(self, client):
        """Should reject invalid latitude (must be -90 to 90)."""
        self._register_device(client)

        response = client.post('/api/destinations',
            data=json.dumps({
                'name': 'Bad Place',
                'latitude': 100,  # Invalid! Max is 90
                'longitude': -74.0060
            }),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_list_destinations(self, client):
        """GET /api/destinations should return user's destinations."""
        self._register_device(client)

        # Create one destination
        client.post('/api/destinations',
            data=json.dumps({
                'name': 'Work',
                'latitude': 40.7580,
                'longitude': -73.9855
            }),
            content_type='application/json'
        )

        # List them
        response = client.get('/api/destinations')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['name'] == 'Work'

    def test_delete_destination(self, client):
        """DELETE /api/destinations/:id should remove destination."""
        self._register_device(client)

        # Create then delete
        create_response = client.post('/api/destinations',
            data=json.dumps({
                'name': 'Temp',
                'latitude': 40.7128,
                'longitude': -74.0060
            }),
            content_type='application/json'
        )
        dest_id = create_response.get_json()['id']

        delete_response = client.delete(f'/api/destinations/{dest_id}')
        assert delete_response.status_code == 200

        # Verify it's gone
        list_response = client.get('/api/destinations')
        assert len(list_response.get_json()) == 0


class TestAlertRoutes:
    """Test the /api/alert endpoints."""

    def _setup_device_and_destination(self, client):
        """Helper: create device + destination (needed for alert tests)."""
        client.post('/api/device')
        response = client.post('/api/destinations',
            data=json.dumps({
                'name': 'Home',
                'latitude': 40.7128,
                'longitude': -74.0060,
                'alert_threshold_minutes': 10
            }),
            content_type='application/json'
        )
        return response.get_json()['id']

    def test_start_alert(self, client):
        """POST /api/alert/start should create an alert session."""
        dest_id = self._setup_device_and_destination(client)

        response = client.post('/api/alert/start',
            data=json.dumps({'destination_id': dest_id}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert 'alert_session_id' in data
        assert data['destination_name'] == 'Home'

    def test_cannot_start_two_alerts(self, client):
        """Should enforce one-alert-at-a-time rule (BR-01)."""
        dest_id = self._setup_device_and_destination(client)

        # Start first alert
        client.post('/api/alert/start',
            data=json.dumps({'destination_id': dest_id}),
            content_type='application/json'
        )

        # Try to start second — should fail
        response = client.post('/api/alert/start',
            data=json.dumps({'destination_id': dest_id}),
            content_type='application/json'
        )

        assert response.status_code == 409  # Conflict

    def test_stop_alert(self, client):
        """POST /api/alert/stop should end the alert session."""
        dest_id = self._setup_device_and_destination(client)

        # Start alert
        start_response = client.post('/api/alert/start',
            data=json.dumps({'destination_id': dest_id}),
            content_type='application/json'
        )
        session_id = start_response.get_json()['alert_session_id']

        # Stop it
        stop_response = client.post('/api/alert/stop',
            data=json.dumps({
                'alert_session_id': session_id,
                'reason': 'user_stopped'
            }),
            content_type='application/json'
        )

        assert stop_response.status_code == 200

    def test_get_active_alert_when_none(self, client):
        """GET /api/alert/active should return active=false when no alert."""
        client.post('/api/device')

        response = client.get('/api/alert/active')
        assert response.status_code == 200
        assert response.get_json()['active'] is False
