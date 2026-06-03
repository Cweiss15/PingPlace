"""
config.py — Application Configuration

This file reads settings from environment variables (.env file).
It's the single source of truth for all configuration values.
Nothing secret is hardcoded here — it all comes from the environment.
"""

import os
from dotenv import load_dotenv

# Load .env file into environment variables
# This means os.environ['GOOGLE_API_KEY'] will work after this line
load_dotenv()


class Config:
    """Base configuration class. All settings live here."""

    # Flask uses this to sign session cookies (must be secret and random)
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-key-change-in-production')

    # Database connection string.
    # Render gives a URL starting with 'postgres://' but SQLAlchemy requires 'postgresql://'
    # The replace() call fixes this automatically — has no effect on SQLite or already-correct URLs.
    _db_url = os.environ.get('DATABASE_URL', 'sqlite:///pingplace.db')
    SQLALCHEMY_DATABASE_URI = _db_url.replace('postgres://', 'postgresql://', 1)

    # Disable a Flask-SQLAlchemy feature that wastes memory
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Google API key — used server-side for Distance Matrix calls
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', '')

    # Geoapify API key — used for address autocomplete in the frontend
    GEOAPIFY_API_KEY = os.environ.get('GEOAPIFY_API_KEY', '')

    # TomTom Traffic API key — used for traffic-aware ETA (car / bus modes)
    TOMTOM_API_KEY = os.environ.get('TOMTOM_TRAFFIC_API_KEY', '')

    # Rate limiting storage (in-memory for development)
    RATELIMIT_STORAGE_URI = "memory://"
