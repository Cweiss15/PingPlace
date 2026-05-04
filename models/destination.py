"""
models/destination.py — Destination Model

A saved place the user wants to travel to (e.g., "Home", "Work").
Stores the Google Place data and the user's alert threshold.

Table structure in PostgreSQL:
+-------------------------+-----------+------------------------------------------+
| Column                  | Type      | Description                              |
+-------------------------+-----------+------------------------------------------+
| id                      | UUID      | Unique identifier                        |
| device_id               | UUID (FK) | Which device owns this destination       |
| name                    | String    | User-friendly label ("Home", "Work")     |
| address                 | String    | Full address from Google Places          |
| place_id                | String    | Google's unique ID for this place        |
| latitude                | Float     | GPS latitude coordinate                  |
| longitude               | Float     | GPS longitude coordinate                 |
| alert_threshold_minutes | Integer   | "Alert me X minutes before arrival"      |
| created_at              | Timestamp | When this destination was saved          |
| updated_at              | Timestamp | Last time this was edited                |
+-------------------------+-----------+------------------------------------------+
"""

import uuid
from datetime import datetime, timezone
from app import db


class Destination(db.Model):
    """
    A saved destination that belongs to a Device.
    Each destination can have its own alert threshold.
    """

    __tablename__ = 'destinations'

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    # Foreign key — links this destination to its parent Device
    # 'db.ForeignKey' creates the database-level relationship
    device_id = db.Column(
        db.String(36),
        db.ForeignKey('devices.id'),
        nullable=False
    )

    # User's label for this place (e.g., "Home")
    name = db.Column(db.String(50), nullable=False)

    # Full address text from Google Places
    address = db.Column(db.String(500), nullable=False)

    # Google's unique identifier for this place
    # (used to get updated info from Google later if needed)
    place_id = db.Column(db.String(300), nullable=False)

    # GPS coordinates (latitude and longitude)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    # How many minutes before arrival to fire the alert
    # Default is 10 minutes, user can change per destination
    alert_threshold_minutes = db.Column(db.Integer, nullable=False, default=10)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationship to AlertSessions
    alert_sessions = db.relationship(
        'AlertSession',
        backref='destination',
        cascade='all, delete-orphan',
        lazy=True
    )

    def to_dict(self):
        """Convert to dictionary for JSON responses."""
        return {
            'id': self.id,
            'device_id': self.device_id,
            'name': self.name,
            'address': self.address,
            'place_id': self.place_id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'alert_threshold_minutes': self.alert_threshold_minutes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
