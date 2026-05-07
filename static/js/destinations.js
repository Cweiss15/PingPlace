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
 * Initialize OpenStreetMap Nominatim Search (Fallback).
 * Since the Google Places API is restricted on this API key, we use Nominatim
 * to geocode the address the user types.
 */
function initPlacesAutocomplete() {
    const container = document.getElementById('place-search-container');
    if (!container) return;
    
    // Clear the container and create a simple manual search input
    container.innerHTML = '';
    
    const searchDiv = document.createElement('div');
    searchDiv.style.display = 'flex';
    searchDiv.style.gap = '8px';
    searchDiv.style.marginBottom = '0.5rem';
    
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'place-search-input';
    input.placeholder = 'Type address & press Enter to search...';
    input.style.marginBottom = '0';
    input.style.flex = '1';
    
    const searchBtn = document.createElement('button');
    searchBtn.textContent = 'Search';
    searchBtn.className = 'btn';
    searchBtn.style.width = 'auto';
    searchBtn.style.padding = '0.75rem 1rem';
    searchBtn.style.marginBottom = '0';
    searchBtn.style.backgroundColor = '#6366f1';
    searchBtn.style.color = 'white';
    
    searchDiv.appendChild(input);
    searchDiv.appendChild(searchBtn);
    container.appendChild(searchDiv);
    
    const performSearch = async () => {
        const query = input.value.trim();
        if (!query) return;
        
        try {
            searchBtn.textContent = '...';
            searchBtn.disabled = true;
            
            // Call Nominatim API (OpenStreetMap)
            const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`, {
                headers: {
                    'Accept-Language': 'en-US,en'
                }
            });
            const data = await response.json();
            
            if (data && data.length > 0) {
                const place = data[0];
                
                selectedPlace = {
                    place_id: place.place_id.toString(),
                    address: place.display_name,
                    latitude: parseFloat(place.lat),
                    longitude: parseFloat(place.lon),
                    suggestedName: place.name || query
                };
                
                // Show the name and threshold inputs
                const nameInput = document.getElementById('destination-name');
                const thresholdDiv = document.querySelector('.threshold-input');
                const saveBtn = document.getElementById('btn-save-destination');
                const cancelBtn = document.getElementById('btn-cancel-destination');
                
                nameInput.style.display = 'block';
                thresholdDiv.style.display = 'flex';
                saveBtn.style.display = 'block';
                if (cancelBtn) cancelBtn.style.display = 'block';
                
                // Pre-fill the name
                nameInput.value = (place.name || query).substring(0, 50);
                nameInput.focus();
                
                // Show destination on map
                if (typeof setDestinationMarker === 'function') {
                    setDestinationMarker(
                        { lat: selectedPlace.latitude, lng: selectedPlace.longitude },
                        selectedPlace.suggestedName
                    );
                }
                
                hideError();
                input.value = place.display_name; // Update input with full formatted address
            } else {
                showError('Location not found. Try a more specific address.');
            }
        } catch (error) {
            console.error('Search error:', error);
            showError('Error searching for location.');
        } finally {
            searchBtn.textContent = 'Search';
            searchBtn.disabled = false;
        }
    };
    
    // Search on Enter key
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            performSearch();
        }
    });
    
    // Search on button click
    searchBtn.addEventListener('click', (e) => {
        e.preventDefault();
        performSearch();
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
