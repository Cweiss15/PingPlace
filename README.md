# PingPlace

A commuter alert web app that wakes you up based on **travel time**, not clock time. Set a destination, configure how many minutes before arrival you want to be alerted, and PingPlace monitors your live location in the background — firing a notification and audio alarm when you're close enough.

🔗 **Live demo:** https://pingplace.onrender.com

---

## How it works

1. Open PingPlace in your phone browser
2. Save a destination (e.g. "Home", "Work")
3. Set an alert threshold — e.g. "alert me 10 minutes before I arrive"
4. Tap **Start Alert**
5. PingPlace polls your GPS every 15–60 seconds (adaptive — more frequent as you get closer), sends your coordinates to the server, and gets back a traffic-aware ETA
6. When ETA ≤ your threshold → notification + audio alarm fires

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python / Flask |
| Database | PostgreSQL (SQLite for local dev) |
| ORM | SQLAlchemy + Flask-Migrate |
| Frontend | Vanilla HTML / CSS / JavaScript |
| ETA — car & bus | TomTom Routing API (traffic-aware) |
| ETA — train fallback | Offline NYC subway graph (Dijkstra) |
| ETA — last resort | OSRM (free, no API key) |
| Hosting | Render (free tier) |

---

## Architecture

The app uses a 3-layer Service-Repository pattern:

```
Browser (polling.js)
    ↓ HTTP
Routes  (routes/)       ← validate input, read cookies, return JSON
    ↓
Services (services/)    ← business logic, ETA orchestration, alert lifecycle
    ↓
Models (models/)        ← SQLAlchemy ORM, database tables
```

No login system — each browser gets a UUID cookie on first visit. All destinations and alert history are tied to that cookie.

---

## Data model

```
Device
  id, cookie_token, created_at, last_seen_at
  └── has many Destinations
  └── has many AlertSessions

Destination
  id, device_id (FK), name, address, place_id
  latitude, longitude, alert_threshold_minutes
  └── has many AlertSessions

AlertSession
  id, device_id (FK), destination_id (FK)
  started_at, ended_at, alert_fired, alert_fired_at
```

Deleting a Device cascades to all its Destinations and AlertSessions. Only one AlertSession per device may be active (ended_at = NULL) at a time.

---

## ETA provider chain (train mode)

Three providers are tried in order — first success wins:

1. **TomTom** — car route time × 1.15 overhead (walk to station + wait). Used most of the time.
2. **Offline subway graph** — Dijkstra on a hardcoded map of ~50 Manhattan/Brooklyn stations. Kicks in if TomTom is unavailable. Returns walking time, train time, transfer count, and step-by-step route.
3. **OSRM** — free driving estimate × 1.15. Last resort, no API key needed.

Car and bus modes use TomTom directly (with live traffic), falling back to OSRM only.

---

## Local setup

**Prerequisites:** Python 3.12+

```bash
git clone https://github.com/your-username/PingPlace.git
cd PingPlace
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy the environment file and fill in your keys:

```bash
cp .env.example .env
```

```env
FLASK_SECRET_KEY=any-random-string
DATABASE_URL=sqlite:///pingplace.db      # or your PostgreSQL URL
TOMTOM_TRAFFIC_API_KEY=your-key-here
GEOAPIFY_API_KEY=your-key-here
```

Run the app:

```bash
python app.py
# → http://localhost:5000
```

---

## API keys needed

| Key | Where to get it | Used for |
|---|---|---|
| `TOMTOM_TRAFFIC_API_KEY` | [developer.tomtom.com](https://developer.tomtom.com) | Car / bus ETA with live traffic |
| `GEOAPIFY_API_KEY` | [geoapify.com](https://www.geoapify.com) | Address autocomplete in the frontend |
| `GOOGLE_API_KEY` | [Google Cloud Console](https://console.cloud.google.com) | Optional — legacy, not currently used |

Train mode works without any API key (falls back to offline subway graph → OSRM).

---

## Running tests

```bash
pytest
```

Tests cover device service, ETA service, subway routing, and API routes. The app factory pattern means each test gets a clean database.

---

## Deployment (Render)

1. Create a new **Web Service** on Render, connected to this repo
2. Set build command: `pip install -r requirements.txt`
3. Set start command: `gunicorn app:app`
4. Add a **PostgreSQL** instance on Render and copy the connection URL into the `DATABASE_URL` environment variable
5. Add your other environment variables in the Render dashboard

Render provides HTTPS automatically.

---

## Project structure

```
PingPlace/
├── app.py                  # App factory, blueprint registration
├── config.py               # Configuration from environment variables
├── extensions.py           # Shared Flask extensions (db, migrate, limiter)
├── models/
│   ├── device.py           # Device model (cookie-based identity)
│   ├── destination.py      # Saved destination model
│   └── alert_session.py    # Alert history model
├── routes/
│   ├── device_routes.py
│   ├── destination_routes.py
│   ├── eta_routes.py       # POST /api/eta — core polling endpoint
│   ├── alert_routes.py     # start / stop / active
│   └── subway_routes.py
├── services/
│   ├── eta_service.py      # TomTom → subway graph → OSRM chain
│   ├── subway_service.py   # Dijkstra on NYC subway graph
│   ├── alert_service.py    # Alert session lifecycle
│   ├── destination_service.py
│   └── device_service.py
├── static/
│   ├── js/
│   │   ├── polling.js      # Adaptive polling loop
│   │   ├── alert.js
│   │   ├── destinations.js
│   │   ├── map.js
│   │   └── app.js
│   └── css/style.css
├── templates/index.html
├── tests/
└── requirements.txt
```
