"""
routes/main_routes.py — Main Routes

Serves the HTML page (the one and only page of the app).

In Flask, a "Blueprint" is a way to organize routes into separate files.
Think of it like a mini-app that gets plugged into the main app.
Without blueprints, all routes would be in one giant file.
"""

from flask import Blueprint, render_template, current_app

# Create a blueprint named 'main'
# __name__ tells Flask where to find templates/static files relative to this file
main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """
    Serve the main (and only) HTML page.

    The @main_bp.route('/') decorator means:
    "When someone visits the root URL (e.g., https://pingplace.onrender.com/),
    run this function and return the result."

    render_template('index.html') tells Flask to:
    1. Look in the templates/ folder
    2. Find index.html
    3. Process any Jinja2 template tags (like {{ variable }})
    4. Return the rendered HTML to the browser

    We pass GOOGLE_API_KEY to the template so the frontend can load
    Google Maps JavaScript API.
    """
    return render_template(
        'index.html',
        google_api_key=current_app.config['GOOGLE_API_KEY'],
        geoapify_api_key=current_app.config['GEOAPIFY_API_KEY']
    )
