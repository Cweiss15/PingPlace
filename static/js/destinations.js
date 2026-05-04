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
 * Initialize Google Places Autocomplete on the search input.
 * Called after the Google Maps script loads.
 *
 * Autocomplete attaches to an <input> and shows a dropdown of matching
 * places as the user types. When they select one, we get a Place object
 * with all the details we need.
 */
function initPlacesAutocomplete() {
    const input = document.getElementById('place-search');
    if (!input || !google || !google.maps || !google.maps.places) return;

    // Create autocomplete instance attached to our input
    const autocomplete = new google.maps.places.Autocomplete(input, {
        // Options to customize the autocomplete behavior:
        fields: ['place_id', 'name', 'formatted_address', 'geometry'],
        // 'fields' limits what data we get back (saves quota/cost)
    });

    // Listen for when user selects a place from the dropdown
    autocomplete.addListener('place_changed', () => {
        const place = autocomplete.getPlace();

        // Validate that the place has geometry (lat/lng)
        if (!place.geometry || !place.geometry.location) {
            showError('Please select a place from the dropdown suggestions.');
            return;
        }

        // Store the selected place
        selectedPlace = {
            place_id: place.place_id,
            address: place.formatted_address,
            latitude: place.geometry.location.lat(),
            longitude: place.geometry.location.lng(),
            suggestedName: place.name
        };

        // Show the name and threshold inputs (hidden until a place is selected)
        const nameInput = document.getElementById('destination-name');
        const thresholdDiv = document.querySelector('.threshold-input');
        const saveBtn = document.getElementById('btn-save-destination');

        nameInput.style.display = 'block';
        thresholdDiv.style.display = 'flex';
        saveBtn.style.display = 'block';

        // Pre-fill the name with the place name (user can change it)
        nameInput.value = place.name.substring(0, 50);  // Max 50 chars
        nameInput.focus();

        // Show destination on map
        if (typeof setDestinationMarker === 'function') {
            setDestinationMarker(
                { lat: selectedPlace.latitude, lng: selectedPlace.longitude },
                place.name
            );
        }

        hideError();
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
    document.getElementById('place-search').value = '';
    document.getElementById('destination-name').value = '';
    document.getElementById('destination-name').style.display = 'none';
    document.querySelector('.threshold-input').style.display = 'none';
    document.getElementById('btn-save-destination').style.display = 'none';
    document.getElementById('threshold-value').value = '10';
    selectedPlace = null;
    clearDestinationMarker();
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
                <button class="btn-icon btn-edit" title="Edit" onclick="editDestination('${dest.id}')">✏️</button>
                <button class="btn-icon btn-delete" title="Delete" onclick="deleteDestination('${dest.id}')">🗑️</button>
            </div>
        `;

        list.appendChild(li);
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
    if (typeof google !== 'undefined' && google.maps && google.maps.places) {
        initPlacesAutocomplete();
        autocompleteInitialized = true;
    } else {
        // Google Maps not ready yet, try again in 500ms
        setTimeout(tryInitAutocomplete, 500);
    }
}

// Set up event listeners when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Save button click
    document.getElementById('btn-save-destination').addEventListener('click', saveDestination);

    // Try to init autocomplete (may need to wait for Google Maps)
    tryInitAutocomplete();
});
