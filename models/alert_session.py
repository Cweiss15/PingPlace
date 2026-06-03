"""
models/alert_session.py — AlertSession Model

Records each time a user activates an alert. Useful for:
1. Debugging — "did the alert fire? when?"
2. History — "how often do I commute to Work?"
3. Analytics — could show commute patterns in the future

Table structure in PostgreSQL:
+----------------+-----------+------------------------------------------+
| Column         | Type      | Description                              |
+----------------+-----------+------------------------------------------+
| id             | UUID      | Unique identifier                        |
| device_id      | UUID (FK) | Which device started this alert          |
| destination_id | UUID (FK) | Which destination was being monitored    |
| started_at     | Timestamp | When "Start Alert" was tapped            |
| ended_at       | Timestamp | When alert ended (stop/fire/error)       |
| alert_fired    | Boolean   | Did the alert actually go off?           |
| alert_fired_at | Timestamp | Exact time the alert fired (if it did)   |
+----------------+-----------+------------------------------------------+
"""

import uuid
from datetime import datetime, timezone
from extensions import db


class AlertSession(db.Model):
    """
    Records one alert lifecycle: start → (monitoring) → stop or fire.
    """

    __tablename__ = 'alert_sessions'

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    device_id = db.Column(
        db.String(36),
        db.ForeignKey('devices.id'),
        nullable=False
    )

    destination_id = db.Column(
        db.String(36),
        db.ForeignKey('destinations.id'),
        nullable=False
    )

    # When the user tapped "Start Alert"
    started_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    # When the alert session ended (nullable — null means still active)
    ended_at = db.Column(db.DateTime, nullable=True)

    # Did the alert actually fire? (vs user manually stopping it)
    alert_fired = db.Column(db.Boolean, default=False)

    # Exact moment the alert fired (null if it never fired)
    alert_fired_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        """Convert to dictionary for JSON responses."""
        return {
            'id': self.id,
            'device_id': self.device_id,
            'destination_id': self.destination_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'alert_fired': self.alert_fired,
            'alert_fired_at': self.alert_fired_at.isoformat() if self.alert_fired_at else None
        }
