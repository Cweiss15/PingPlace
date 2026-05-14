/**
 * static/js/destinations.js — Destination Management & Google Places Autocomplete
 *
 * This file handles:
 * 1. Google Places Autocomplete (search-as-you-type for locations)
 * 2. Saving a new destination to the server
 * 3. Rendering the destination list in the UI
 * 4. Editing and deleting destinations
 *
 * GOOGLE PLACES AUTOCOMPLETE:
 * When you type in the search box, Google suggests matching places
 * (like Google Maps search). When you select one, we get its:
 * - name, address, latitude, longitude, place_id
 * This is way better than asking users to type coordinates!
 */

// Holds the selected place from autocomplete (before saving)
let selectedPlace = null;

/**
 * Initialize Geoapify Autocomplete Search.
 *
 * Calls https://api.geoapify.com/v1/geocode/autocomplete as the user types,
 * showing a dropdown of matching places. Selecting one populates selectedPlace
 * and reveals the name / threshold / save form.
 *
 * Debounced at 300 ms to avoid hammering the API on every keystroke.
 */
function initPlacesAutocomplete() {
    const container = document.getElementById('place-search-container');
    if (!container) return;

    // ── Build the search input ────────────────────────────────────────────────
    container.innerHTML = '';

    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'position:relative; margin-bottom:0.5rem;';

    const input = document.createElement('input');
    input.type = 'text';
    input.id = 'geoapify-search-input';
    input.className = 'place-search-input';
    input.placeholder = 'Search for a place…';
    input.autocomplete = 'off';
    input.setAttribute('data-testid', 'place-search-input');

    // ── Build the dropdown list ───────────────────────────────────────────────
    const dropdown = document.createElement('ul');
    dropdown.id = 'geoapify-suggestions';
    dropdown.style.cssText = [
        'position:absolute',
        'top:100%',
        'left:0',
        'right:0',
        'z-index:9999',
        'margin:2px 0 0',
        'padding:0',
        'list-style:none',
        'background:#1e1e2e',
        'border:1px solid #6366f1',
        'border-radius:8px',
        'box-shadow:0 8px 24px rgba(0,0,0,.5)',
        'max-height:240px',
        'overflow-y:auto',
        'display:none'
    ].join(';');

    wrapper.appendChild(input);
    wrapper.appendChild(dropdown);
    container.appendChild(wrapper);

    // ── Helper: render suggestion items ──────────────────────────────────────
    function renderSuggestions(features) {
        dropdown.innerHTML = '';

        if (!features || features.length === 0) {
            dropdown.style.display = 'none';
            return;
        }

        features.forEach((feature, idx) => {
            const props = feature.properties;
            const li = document.createElement('li');
            li.dataset.idx = idx;
            li.style.cssText = [
                'padding:10px 14px',
                'cursor:pointer',
                'border-bottom:1px solid rgba(255,255,255,.07)',
                'color:#e2e8f0',
                'font-size:0.875rem',
                'line-height:1.4',
                'transition:background 0.15s'
            ].join(';');

            // Bold the primary name, dim the secondary address
            const primary = escapeHtml(props.name || props.formatted || '');
            const secondary = escapeHtml(
                props.name && props.formatted && props.formatted !== props.name
                    ? props.formatted
                    : (props.country || '')
            );

            li.innerHTML = `<strong>${primary}</strong>${secondary ? `<br><span style="color:#94a3b8;font-size:0.8rem">${secondary}</span>` : ''}`;

            li.addEventListener('mouseenter', () => { li.style.background = 'rgba(99,102,241,.25)'; });
            li.addEventListener('mouseleave', () => { li.style.background = ''; });

            li.addEventListener('mousedown', (e) => {
                // Use mousedown (not click) so it fires before the input blur
                e.preventDefault();
                selectSuggestion(feature);
            });

            dropdown.appendChild(li);
        });

        dropdown.style.display = 'block';
    }

    // ── Helper: when a suggestion is chosen ──────────────────────────────────
    function selectSuggestion(feature) {
        const props = feature.properties;
        const [lng, lat] = feature.geometry.coordinates;

        selectedPlace = {
            place_id: props.place_id || props.osm_id || `geo_${lat}_${lng}`,
            address: props.formatted || props.name || '',
            latitude: lat,
            longitude: lng,
            suggestedName: props.name || props.city || props.formatted || ''
        };

        // Fill the search input with the chosen address
        input.value = props.formatted || props.name || '';
        dropdown.style.display = 'none';

        // Show the name / threshold / save form
        const nameInput = document.getElementById('destination-name');
        const thresholdDiv = document.querySelector('.threshold-input');
        const saveBtn = document.getElementById('btn-save-destination');
        const cancelBtn = document.getElementById('btn-cancel-destination');

        nameInput.style.display = 'block';
        thresholdDiv.style.display = 'flex';
        saveBtn.style.display = 'block';
        if (cancelBtn) cancelBtn.style.display = 'block';

        // Pre-fill label with the place's short name
        nameInput.value = selectedPlace.suggestedName.substring(0, 50);
        nameInput.focus();

        // Drop a pin on the map
        if (typeof setDestinationMarker === 'function') {
            setDestinationMarker(
                { lat: selectedPlace.latitude, lng: selectedPlace.longitude },
                selectedPlace.suggestedName
            );
        }

        // ── Show straight-line distance from current location ─────────────────
        showDistanceFromCurrentLocation(selectedPlace.latitude, selectedPlace.longitude, selectedPlace.suggestedName);

        hideError();
    }

    // ── Fetch suggestions from Geoapify (debounced) ───────────────────────────
    let debounceTimer = null;

    async function fetchSuggestions(query) {
        if (!query || query.length < 2) {
            dropdown.style.display = 'none';
            return;
        }

        try {
            const url = new URL('https://api.geoapify.com/v1/geocode/autocomplete');
            url.searchParams.set('text', query);
            url.searchParams.set('apiKey', GEOAPIFY_API_KEY);
            url.searchParams.set('limit', '6');
            url.searchParams.set('format', 'geojson');

            const res = await fetch(url.toString());
            if (!res.ok) throw new Error(`Geoapify error: ${res.status}`);
            const data = await res.json();
            renderSuggestions(data.features || []);
        } catch (err) {
            console.error('Autocomplete fetch failed:', err);
            dropdown.style.display = 'none';
        }
    }

    // ── Wire up input events ──────────────────────────────────────────────────
    input.addEventListener('input', () => {
        const query = input.value.trim();
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => fetchSuggestions(query), 300);
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            dropdown.style.display = 'none';
        }
    });

    // Hide dropdown when focus leaves the search area entirely
    input.addEventListener('blur', () => {
        setTimeout(() => { dropdown.style.display = 'none'; }, 150);
    });
}

/**
 * Save a new destination to the server.
 * Collects data from the form inputs and sends a POST request.
 */
async function saveDestination() {
    if (!selectedPlace) {
        showError('Please search and select a place first.');
        return;
    }

    const name = document.getElementById('destination-name').value.trim();
    const threshold = parseInt(document.getElementById('threshold-value').value);

    // Validate inputs
    if (!name || name.length < 1 || name.length > 50) {
        showError('Please enter a name (1-50 characters).');
        return;
    }

    if (isNaN(threshold) || threshold < 1 || threshold > 120) {
        showError('Threshold must be between 1 and 120 minutes.');
        return;
    }

    try {
        const response = await fetch('/api/destinations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                address: selectedPlace.address,
                place_id: selectedPlace.place_id,
                latitude: selectedPlace.latitude,
                longitude: selectedPlace.longitude,
                alert_threshold_minutes: threshold
            })
        });

        if (!response.ok) {
            const err = await response.json();
            showError(err.error || 'Failed to save destination.');
            return;
        }

        const newDest = await response.json();

        // Add to local state and update UI
        appState.destinations.push(newDest);
        renderDestinationList();
        updateDestinationSelect();

        // Auto-select the newly saved destination in the dropdown
        const select = document.getElementById('destination-select');
        if (select) {
            select.value = newDest.id;
            // Trigger the change event so buttons enable
            select.dispatchEvent(new Event('change'));
        }

        // Reset the form
        resetDestinationForm();
        hideError();

    } catch (error) {
        showError('Network error. Please try again.');
        console.error('Save destination error:', error);
    }
}

/**
 * Reset the destination form to its initial state.
 */
function resetDestinationForm() {
    // Reset the search element
    const container = document.getElementById('place-search-container');
    if (container) {
        const input = container.querySelector('input[type="text"]');
        if (input) {
            input.value = '';
        }
    }
    document.getElementById('destination-name').value = '';
    document.getElementById('destination-name').style.display = 'none';
    document.querySelector('.threshold-input').style.display = 'none';
    document.getElementById('btn-save-destination').style.display = 'none';
    const cancelBtn = document.getElementById('btn-cancel-destination');
    if (cancelBtn) cancelBtn.style.display = 'none';
    document.getElementById('threshold-value').value = '10';
    selectedPlace = null;
    hideDistanceBanner();
    if (typeof clearDestinationMarker === 'function') {
        clearDestinationMarker();
    }
}

/**
 * Render the list of saved destinations in the UI.
 * Creates HTML for each destination with edit/delete buttons.
 */
function renderDestinationList() {
    const list = document.getElementById('destination-list');
    list.innerHTML = '';  // Clear existing items

    if (appState.destinations.length === 0) {
        list.innerHTML = '<li class="no-destinations">No saved destinations yet. Search above to add one!</li>';
        return;
    }

    appState.destinations.forEach(dest => {
        const li = document.createElement('li');
        li.className = 'destination-item';
        li.dataset.id = dest.id;

        li.innerHTML = `
            <div class="destination-info">
                <div class="destination-name">${escapeHtml(dest.name)}</div>
                <div class="destination-address">${escapeHtml(dest.address || '')}</div>
                <div class="destination-threshold">Alert at ${dest.alert_threshold_minutes} min</div>
            </div>
            <div class="destination-actions">
                <button class="btn-icon btn-edit" title="Edit" data-id="${dest.id}">✏️</button>
                <button class="btn-icon btn-delete" title="Delete" data-id="${dest.id}">🗑️</button>
            </div>
        `;

        list.appendChild(li);
    });

    // Attach event listeners safely
    document.querySelectorAll('.btn-edit').forEach(btn => {
        btn.addEventListener('click', (e) => {
            editDestination(e.target.closest('button').dataset.id);
        });
    });

    document.querySelectorAll('.btn-delete').forEach(btn => {
        btn.addEventListener('click', (e) => {
            deleteDestination(e.target.closest('button').dataset.id);
        });
    });
}

/**
 * Delete a destination from the server and UI.
 *
 * @param {string} destinationId - UUID of destination to delete
 */
async function deleteDestination(destinationId) {
    // Confirm before deleting
    if (!confirm('Delete this destination?')) return;

    try {
        const response = await fetch(`/api/destinations/${destinationId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            showError('Failed to delete destination.');
            return;
        }

        // Remove from local state
        appState.destinations = appState.destinations.filter(d => d.id !== destinationId);
        renderDestinationList();
        updateDestinationSelect();

    } catch (error) {
        showError('Network error. Please try again.');
        console.error('Delete error:', error);
    }
}

/**
 * Edit a destination's threshold.
 * Uses a simple prompt for now (could be a modal later).
 *
 * @param {string} destinationId - UUID of destination to edit
 */
async function editDestination(destinationId) {
    const dest = appState.destinations.find(d => d.id === destinationId);
    if (!dest) return;

    const newThreshold = prompt(
        `Alert threshold for "${dest.name}" (1-120 minutes):`,
        dest.alert_threshold_minutes
    );

    if (newThreshold === null) return;  // User cancelled

    const threshold = parseInt(newThreshold);
    if (isNaN(threshold) || threshold < 1 || threshold > 120) {
        showError('Threshold must be between 1 and 120 minutes.');
        return;
    }

    try {
        const response = await fetch(`/api/destinations/${destinationId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ alert_threshold_minutes: threshold })
        });

        if (!response.ok) {
            showError('Failed to update destination.');
            return;
        }

        const updated = await response.json();

        // Update local state
        const index = appState.destinations.findIndex(d => d.id === destinationId);
        if (index !== -1) {
            appState.destinations[index] = updated;
        }

        renderDestinationList();
        updateDestinationSelect();
        hideError();

    } catch (error) {
        showError('Network error. Please try again.');
        console.error('Edit error:', error);
    }
}

/**
 * Calculate straight-line (haversine) distance between two lat/lng points.
 * Returns distance in km.
 *
 * @param {number} lat1
 * @param {number} lng1
 * @param {number} lat2
 * @param {number} lng2
 * @returns {number} Distance in km
 */
function haversineDistance(lat1, lng1, lat2, lng2) {
    const R = 6371; // Earth radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a =
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/**
 * Get user's current GPS location, calculate straight-line distance to the
 * given destination coordinates, and display a banner in the status card.
 *
 * @param {number} destLat
 * @param {number} destLng
 * @param {string} destName
 */
function showDistanceFromCurrentLocation(destLat, destLng, destName) {
    const banner = document.getElementById('distance-banner');
    if (!banner) return;

    banner.textContent = '📍 Getting your location…';
    banner.style.display = 'block';

    if (!navigator.geolocation) {
        banner.textContent = '⚠️ Geolocation not available';
        return;
    }

    navigator.geolocation.getCurrentPosition(
        (pos) => {
            const km = haversineDistance(
                pos.coords.latitude, pos.coords.longitude,
                destLat, destLng
            );
            const miles = km * 0.621371;
            const distStr = km < 1
                ? `${Math.round(km * 1000)} m`
                : `${km.toFixed(1)} km (${miles.toFixed(1)} mi)`;
            banner.innerHTML = `📍 <strong>${escapeHtml(destName)}</strong> is <strong>${distStr}</strong> away (straight line)`;
        },
        () => {
            banner.textContent = '⚠️ Location permission needed to show distance';
        },
        { enableHighAccuracy: false, timeout: 8000, maximumAge: 60000 }
    );
}

/**
 * Hide the distance banner.
 */
function hideDistanceBanner() {
    const banner = document.getElementById('distance-banner');
    if (banner) banner.style.display = 'none';
}

/**
 * Escape HTML special characters to prevent XSS attacks.
 *
 * WHY THIS MATTERS (Security):
 * If a destination name contains something like <script>alert('hacked')</script>,
 * and we insert it directly into innerHTML, the browser would EXECUTE that script.
 * This is called Cross-Site Scripting (XSS). By escaping < > & " ' characters,
 * they display as text instead of being interpreted as HTML.
 *
 * @param {string} text - Raw text that might contain HTML characters
 * @returns {string} Safe text with HTML entities escaped
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;  // textContent automatically escapes HTML
    return div.innerHTML;
}

// ============ EVENT LISTENERS ============

// Initialize autocomplete after Google Maps loads (slight delay to ensure API ready)
// We use a flag to avoid double-initialization
let autocompleteInitialized = false;

function tryInitAutocomplete() {
    if (autocompleteInitialized) return;
    // We no longer rely on Google Places API, so we initialize our Nominatim fallback immediately
    initPlacesAutocomplete();
    autocompleteInitialized = true;
}

// Set up event listeners when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Save button click
    document.getElementById('btn-save-destination').addEventListener('click', saveDestination);

    // Cancel button click
    const cancelBtn = document.getElementById('btn-cancel-destination');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', (e) => {
            e.preventDefault();
            resetDestinationForm();
        });
    }

    // Try to init autocomplete
    tryInitAutocomplete();
});
