/**
 * static/js/map.js — Google Maps Integration
 *
 * This file handles:
 * 1. Initializing the Google Map (called by the Maps API callback)
 * 2. Showing the user's location as a blue dot
 * 3. Showing the destination as a red pin
 * 4. Updating markers when location changes
 *
 * IMPORTANT: This file exposes the global function `initMap` which Google Maps
 * calls automatically when its script finishes loading (because we specified
 * callback=initMap in the script tag).
 */

// Module-level variables for map and markers
let map = null;
let userMarker = null;
let destinationMarker = null;

/**
 * initMap() — Called by Google Maps API when it's ready.
 *
 * This function is the callback specified in the <script> tag:
 * <script src="...&callback=initMap">
 *
 * We initialize the map centered on a default location (will be updated
 * once we get the user's actual GPS position).
 */
function initMap() {
    // Default center: New York City (will be overridden by user's GPS)
    const defaultCenter = { lat: 40.7128, lng: -74.0060 };

    // Create the Google Map instance
    map = new google.maps.Map(document.getElementById('map'), {
        center: defaultCenter,
        zoom: 14,
        // Map options for cleaner look
        mapTypeControl: false,     // Hide satellite/terrain toggle
        streetViewControl: false,   // Hide street view pegman
        fullscreenControl: false,   // Hide fullscreen button
        zoomControl: true
    });

    // Try to center on user's location immediately
    getUserLocation().then(position => {
        if (position) {
            const userLatLng = {
                lat: position.coords.latitude,
                lng: position.coords.longitude
            };
            map.setCenter(userLatLng);
            setUserMarker(userLatLng);
        }
    });
}

/**
 * Get the user's current GPS position using the Browser Geolocation API.
 *
 * navigator.geolocation.getCurrentPosition() asks the browser for GPS.
 * It returns a Promise for cleaner async/await usage.
 *
 * Returns: Position object or null if unavailable.
 */
function getUserLocation() {
    return new Promise((resolve) => {
        if (!navigator.geolocation) {
            resolve(null);
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (position) => resolve(position),
            () => resolve(null),  // Silently handle error (permission denied, etc.)
            {
                enableHighAccuracy: true,  // Use GPS if available (more accurate)
                timeout: 10000,            // Wait max 10 seconds
                maximumAge: 30000          // Accept cached position up to 30 seconds old
            }
        );
    });
}

/**
 * Set or update the user's position marker (blue dot).
 *
 * @param {Object} latLng - { lat: number, lng: number }
 */
function setUserMarker(latLng) {
    if (userMarker) {
        // Marker already exists, just move it
        userMarker.setPosition(latLng);
    } else {
        // Create a new marker with a blue circle icon
        userMarker = new google.maps.Marker({
            position: latLng,
            map: map,
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 8,
                fillColor: '#4285F4',   // Google Blue
                fillOpacity: 1,
                strokeColor: '#ffffff',
                strokeWeight: 2
            },
            title: 'Your location'
        });
    }
}

/**
 * Set or update the destination marker (red pin).
 *
 * @param {Object} latLng - { lat: number, lng: number }
 * @param {string} name - Destination name for the tooltip
 */
function setDestinationMarker(latLng, name) {
    if (destinationMarker) {
        destinationMarker.setPosition(latLng);
        destinationMarker.setTitle(name);
    } else {
        destinationMarker = new google.maps.Marker({
            position: latLng,
            map: map,
            title: name
            // Uses default red pin icon
        });
    }

    // Adjust map to show both user and destination
    fitMapToBothMarkers();
}

/**
 * Remove the destination marker from the map.
 */
function clearDestinationMarker() {
    if (destinationMarker) {
        destinationMarker.setMap(null);
        destinationMarker = null;
    }
}

/**
 * Fit the map bounds to show both the user and destination markers.
 * Uses LatLngBounds to calculate the perfect zoom level.
 */
function fitMapToBothMarkers() {
    if (!userMarker || !destinationMarker) return;

    const bounds = new google.maps.LatLngBounds();
    bounds.extend(userMarker.getPosition());
    bounds.extend(destinationMarker.getPosition());
    map.fitBounds(bounds, { padding: 50 });  // 50px padding around edges
}

/**
 * Update the map with the latest user position.
 * Called by polling.js each time we get a new GPS fix.
 *
 * @param {number} lat - Latitude
 * @param {number} lng - Longitude
 */
function updateMapUserPosition(lat, lng) {
    const latLng = { lat, lng };
    setUserMarker(latLng);

    // If there's an active destination, also show the route
    if (appState.activeAlert.destinationId) {
        const dest = appState.destinations.find(
            d => d.id === appState.activeAlert.destinationId
        );
        if (dest) {
            setDestinationMarker(
                { lat: dest.latitude, lng: dest.longitude },
                dest.name
            );
        }
    }
}
