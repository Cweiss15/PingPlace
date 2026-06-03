"""
extensions.py — Shared Flask extensions.

This module holds the Flask extension instances used across the app.
It avoids circular imports by letting routes, services, and models import
extensions without importing the application factory itself.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Database ORM — lets you use Python classes instead of raw SQL
db = SQLAlchemy()

# Database migrations — tracks schema changes over time
migrate = Migrate()

# Rate limiter — prevents API abuse (e.g., max 60 requests/minute per IP)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60 per minute"]
)
