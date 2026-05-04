"""
tests/test_device_service.py — Tests for Device Registration

Tests the device service which handles:
- Creating new devices (first visit)
- Retrieving existing devices (return visit)

TESTING PATTERN:
Each test follows Arrange-Act-Assert (AAA):
1. Arrange: Set up the data/conditions
2. Act: Call the function being tested
3. Assert: Check the result is correct
"""

from models.device import Device
from services.device_service import get_or_create_device, get_device_by_id


class TestGetOrCreateDevice:
    """Tests for the get_or_create_device function."""

    def test_creates_new_device_when_no_token(self, app, db_session):
        """First-time visitor: should create a new device."""
        with app.app_context():
            device = get_or_create_device(None)

            assert device is not None
            assert device.id is not None
            assert device.cookie_token is not None

    def test_creates_new_device_with_new_token(self, app, db_session):
        """Unrecognized token: should create a new device."""
        with app.app_context():
            device = get_or_create_device('nonexistent-token-12345')

            assert device is not None
            assert device.cookie_token != 'nonexistent-token-12345'

    def test_returns_existing_device_for_known_token(self, app, db_session):
        """Return visitor: should find and return existing device."""
        with app.app_context():
            # Arrange: create a device first
            device1 = get_or_create_device(None)
            token = device1.cookie_token

            # Act: look up with that token
            device2 = get_or_create_device(token)

            # Assert: same device returned
            assert device2.id == device1.id

    def test_updates_last_seen(self, app, db_session):
        """Should update last_seen_at when device is retrieved."""
        with app.app_context():
            device = get_or_create_device(None)
            original_last_seen = device.last_seen_at

            # Retrieve again
            device2 = get_or_create_device(device.cookie_token)

            assert device2.last_seen_at >= original_last_seen


class TestGetDeviceById:
    """Tests for the get_device_by_id function."""

    def test_returns_device_for_valid_id(self, app, db_session):
        """Should return the device when ID exists."""
        with app.app_context():
            device = get_or_create_device(None)
            found = get_device_by_id(device.id)

            assert found is not None
            assert found.id == device.id

    def test_returns_none_for_invalid_id(self, app, db_session):
        """Should return None when ID doesn't exist."""
        with app.app_context():
            found = get_device_by_id('00000000-0000-0000-0000-000000000000')

            assert found is None
