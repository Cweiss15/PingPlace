"""
app.py — Application Entry Point

This is where everything starts. It creates the Flask app,
connects the database, registers all route blueprints,
and sets up security middleware.

Run with: python app.py
Or in production: gunicorn app:app
"""

from flask import Flask, make_response
from flask_cors import CORS
from config import Config
from extensions import db, migrate, limiter

# ============================================================
# Shared Flask extension instances are created in extensions.py.
# This prevents circular imports between app.py and route/service modules.
# ============================================================


def create_app():
    """
    App Factory Pattern — creates and configures a Flask app instance.

    Why a factory function instead of just creating the app at module level?
    1. Makes testing easier (create fresh app for each test)
    2. Allows multiple configurations (dev, test, production)
    3. Avoids circular import issues
    """
    app = Flask(__name__)

    # Load configuration from config.py
    app.config.from_object(Config)

    # ============================================================
    # Initialize extensions with this app instance
    # ============================================================
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    # CORS — allow requests from same origin only (security)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # ============================================================
    # Security Headers (applied to every response)
    # ============================================================
    @app.after_request
    def set_security_headers(response):
        """
        Add security headers to every HTTP response.
        These protect against common web attacks.
        """
        # Prevent the browser from guessing content types (stops some attacks)
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # Prevent your site from being embedded in an iframe (clickjacking protection)
        response.headers['X-Frame-Options'] = 'DENY'

        # Control what info is sent in the Referer header
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Force HTTPS for 1 year (Render provides HTTPS)
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        # Content Security Policy — controls what resources the page can load
        # 'self' = only from our domain, plus Google Maps (display) and Nominatim (search)
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' https://maps.googleapis.com https://maps.gstatic.com 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
            "img-src 'self' https://*.googleapis.com https://*.gstatic.com https://*.google.com data:; "
            "connect-src 'self' https://maps.googleapis.com https://nominatim.openstreetmap.org https://api.geoapify.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "frame-src https://www.google.com https://maps.google.com; "
            "worker-src blob:;"
        )

        return response

    # ============================================================
    # Register route blueprints (each file in routes/ folder)
    # ============================================================
    from routes.main_routes import main_bp
    from routes.device_routes import device_bp
    from routes.destination_routes import destination_bp
    from routes.eta_routes import eta_bp
    from routes.alert_routes import alert_bp
    from routes.subway_routes import subway_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(device_bp, url_prefix='/api')
    app.register_blueprint(destination_bp, url_prefix='/api')
    app.register_blueprint(eta_bp, url_prefix='/api')
    app.register_blueprint(alert_bp, url_prefix='/api')
    app.register_blueprint(subway_bp, url_prefix='/api')

    # ============================================================
    # Create database tables if they don't exist
    # ============================================================
    with app.app_context():
        # Import models so SQLAlchemy knows about them
        from models import device, destination, alert_session  # noqa: F401
        db.create_all()

    return app


# ============================================================
# Create the app instance
# ============================================================
app = create_app()

# Only run the development server if this file is run directly
# (not when imported by gunicorn or tests)
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
