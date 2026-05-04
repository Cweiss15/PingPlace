"""
models/device.py — Device Model

Represents a user identified by a browser cookie.
Instead of login/password, PingPlace uses a unique cookie to recognize
returning visitors. This table stores one row per unique browser.

Table structure in PostgreSQL:
+-------------+-----------+------------------------------------------+
| Column      | Type      | Description                              |
+-------------+-----------+------------------------------------------+
| id          | UUID      | Unique identifier (primary key)          |
| cookie_token| UUID      | The value stored in the browser cookie   |
| created_at  | Timestamp | When this device first visited           |
| last_seen_at| Timestamp | When this device last made a request     |
+-------------+-----------+------------------------------------------+
"""

import uuid
from datetime import datetime, timezone
from app import db


class Device(db.Model):
    """
    A Device = one browser on one phone/computer.
    Each gets a unique cookie_token stored in their browser.
    """

    __tablename__ = 'devices'  # The actual table name in PostgreSQL

    # Primary key — unique ID for each device (UUID = universally unique)
    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    # The token we store in the browser cookie
    # 'unique=True' means no two rows can have the same value
    cookie_token = db.Column(
        db.String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4())
    )

    # When this device first visited PingPlace
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    # Updated every time the device makes a request
    last_seen_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships — tells SQLAlchemy "a Device has many Destinations"
    # 'backref' creates a reverse link: destination.device gives the parent Device
    # 'cascade' means: if you delete a Device, delete its Destinations too
    destinations = db.relationship(
        'Destination',
        backref='device',
        cascade='all, delete-orphan',
        lazy=True
    )

    alert_sessions = db.relationship(
        'AlertSession',
        backref='device',
        cascade='all, delete-orphan',
        lazy=True
    )

    def to_dict(self):
        """Convert to dictionary for JSON responses."""
        return {
            'id': self.id,
            'cookie_token': self.cookie_token,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_seen_at': self.last_seen_at.isoformat() if self.last_seen_at else None
        }
