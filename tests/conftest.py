"""
tests/conftest.py — Pytest Configuration & Shared Fixtures

WHAT ARE FIXTURES?
Fixtures are reusable setup/teardown functions that pytest runs before/after
your tests. They provide things tests need (like a test client or database).

The @pytest.fixture decorator marks a function as a fixture.
When a test function has a parameter with the same name as a fixture,
pytest automatically calls the fixture and passes its return value.

Example:
    def test_something(client):  ← pytest sees 'client', finds the fixture below
        response = client.get('/')
"""

import pytest
from app import create_app
from extensions import db


@pytest.fixture
def app():
    """
    Create a Flask app configured for testing.

    Key differences from production:
    - TESTING=True: Flask gives better error messages
    - SQLite in-memory DB: Fast, disposable, no cleanup needed
    - WTF_CSRF_ENABLED=False: Disable CSRF for easier testing
    """
    test_app = create_app()
    test_app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',  # In-memory DB
        'WTF_CSRF_ENABLED': False,
        'RATELIMIT_ENABLED': False  # Disable rate limiting in tests
    })

    # Create all database tables
    with test_app.app_context():
        db.create_all()

    yield test_app  # 'yield' means: give this to the test, then run cleanup after

    # Cleanup: drop all tables
    with test_app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    """
    A test client for making HTTP requests without starting a real server.

    Usage in tests:
        response = client.get('/api/destinations')
        assert response.status_code == 200
    """
    return app.test_client()


@pytest.fixture
def db_session(app):
    """
    Provide direct database access for tests that need to set up data.
    """
    with app.app_context():
        yield db.session
