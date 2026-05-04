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

    # Database connection string
    # Format: postgresql://user:password@host:port/database_name
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///pingplace.db')

    # Disable a Flask-SQLAlchemy feature that wastes memory
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Google API key — used server-side for Distance Matrix calls
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', '')

    # Rate limiting storage (in-memory for development)
    RATELIMIT_STORAGE_URI = "memory://"
