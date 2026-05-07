/**
 * static/js/app.js — Main Application Orchestrator
 *
 * This is the "conductor" of the frontend. It:
 * 1. Manages the global app state (what's happening right now)
 * 2. Initializes other modules (map, polling, alert, destinations)
 * 3. Handles the device cookie registration on page load
 * 4. Coordinates between modules (e.g., when polling detects alert threshold)
 *
 * GLOBAL STATE OBJECT:
 * Instead of scattering variables everywhere, we keep ONE object
 * that tracks everything. Any module can read/update it.
 */

// ============ GLOBAL STATE ============
const appState = {
    deviceId: null,          // Set after device registration
    destinations: [],        // Array of saved destinations
    travelMode: 'car',       // 'car' | 'bus' | 'train'
    activeAlert: {
        sessionId: null,     // UUID from server when alert starts
        destinationId: null,
        destinationName: '',
        thresholdMinutes: 10,
        currentEta: null,    // Latest ETA in minutes
        lastUpdated: null,   // Timestamp of last ETA update
        state: 'IDLE'        // 'IDLE' | 'POLLING' | 'FIRED'
    },
    trackingMode: false      // True = monitor ETA without alarm
};

/**
 * Called when the page finishes loading.
 * Registers the device (creates cookie if first visit), then loads destinations.
 */
async function initApp() {
    try {
        // Step 1: Register device (get or create cookie)
        const response = await fetch('/api/device', { method: 'POST' });
        const data = await response.json();
        appState.deviceId = data.device_id;

        // Step 2: Load saved destinations
        await loadDestinations();

        // Step 3: Check if there's an active alert (page might have been refreshed)
        await checkActiveAlert();

        // Step 4: Set up UI event listeners
        setupEventListeners();

    } catch (error) {
        showError('Failed to initialize app. Please refresh the page.');
        console.error('Init error:', error);
    }
}

/**
 * Load all saved destinations from the server and populate the UI.
 */
async function loadDestinations() {
    try {
        const response = await fetch('/api/destinations');
        if (response.ok) {
            appState.destinations = await response.json();
            renderDestinationList();
            updateDestinationSelect();
        }
    } catch (error) {
        console.error('Failed to load destinations:', error);
    }
}

/**
 * Check if there's an active alert (handles page refreshes during commute).
 */
async function checkActiveAlert() {
    try {
        const response = await fetch('/api/alert/active');
        const data = await response.json();

        if (data.active) {
            // Resume the active alert
            appState.activeAlert.sessionId = data.alert_session_id;
            appState.activeAlert.destinationId = data.destination_id;
            appState.activeAlert.destinationName = data.destination_name;
            appState.activeAlert.thresholdMinutes = data.threshold_minutes;
            appState.activeAlert.state = 'POLLING';
            updateUIForState('POLLING');
            startPolling();  // Resume polling (defined in polling.js)
        }
    } catch (error) {
        console.error('Failed to check active alert:', error);
    }
}

/**
 * Set up click handlers for all buttons.
 */
function setupEventListeners() {
    // Start Alert button
    document.getElementById('btn-start-alert').addEventListener('click', handleStartAlert);

    // Stop Alert button
    document.getElementById('btn-stop-alert').addEventListener('click', handleStopAlert);

    // Track Only button
    document.getElementById('btn-track-only').addEventListener('click', handleTrackOnly);

    // Dismiss Alert buttons (both the small one and the overlay one)
    document.getElementById('btn-dismiss-alert').addEventListener('click', handleDismissAlert);
    document.getElementById('btn-dismiss-overlay').addEventListener('click', handleDismissAlert);

    // Destination select dropdown — enable/disable buttons based on selection
    document.getElementById('destination-select').addEventListener('change', function() {
        const hasSelection = this.value !== '';
        document.getElementById('btn-start-alert').disabled = !hasSelection;
        document.getElementById('btn-track-only').disabled = !hasSelection;
    });

    // Transport mode picker
    document.querySelectorAll('.transport-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            appState.travelMode = btn.dataset.mode;
            document.querySelectorAll('.transport-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
}

/**
 * Handle "Start Alert" button click.
 * 1. Request location permission
 * 2. Tell server to create alert session
 * 3. Start polling
 */
async function handleStartAlert() {
    const destinationId = document.getElementById('destination-select').value;
    if (!destinationId) return;

    // Request location permission first
    const hasPermission = await requestLocationPermission();
    if (!hasPermission) return;

    try {
        // Tell server to start alert session
        const response = await fetch('/api/alert/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ destination_id: destinationId })
        });

        if (!response.ok) {
            const err = await response.json();
            showError(err.error || 'Failed to start alert');
            return;
        }

        const data = await response.json();

        // Update state
        appState.activeAlert.sessionId = data.alert_session_id;
        appState.activeAlert.destinationId = destinationId;
        appState.activeAlert.destinationName = data.destination_name;
        appState.activeAlert.thresholdMinutes = data.threshold_minutes;
        appState.activeAlert.state = 'POLLING';
        appState.trackingMode = false;

        // Update UI and start polling
        updateUIForState('POLLING');
        startPolling();  // Defined in polling.js
        hideError();

    } catch (error) {
        showError('Network error. Please try again.');
        console.error('Start alert error:', error);
    }
}

/**
 * Handle "Stop Alert" button click.
 */
async function handleStopAlert() {
    await stopCurrentAlert('user_stopped');
}

/**
 * Handle "Track Only" button click.
 * Same as Start Alert but without firing notifications.
 */
async function handleTrackOnly() {
    const destinationId = document.getElementById('destination-select').value;
    if (!destinationId) return;

    const hasPermission = await requestLocationPermission();
    if (!hasPermission) return;

    // Find the destination to get its details
    const dest = appState.destinations.find(d => d.id === destinationId);

    // Track mode doesn't create a server-side alert session
    appState.activeAlert.destinationId = destinationId;
    appState.activeAlert.destinationName = dest ? dest.name : 'Destination';
    appState.activeAlert.thresholdMinutes = dest ? dest.alert_threshold_minutes : 10;
    appState.activeAlert.state = 'POLLING';
    appState.trackingMode = true;  // This flag prevents alert from firing

    updateUIForState('POLLING');
    startPolling();
    hideError();
}

/**
 * Handle alert dismissal (after it fires).
 */
async function handleDismissAlert() {
    stopAlertSound();  // Defined in alert.js
    hideAlertOverlay();

    if (appState.activeAlert.sessionId) {
        await stopCurrentAlert('alert_fired');
    } else {
        // Was in tracking mode, just reset
        resetAlertState();
    }
}

/**
 * Stop the current alert and notify the server.
 */
async function stopCurrentAlert(reason) {
    stopPolling();  // Defined in polling.js

    if (appState.activeAlert.sessionId) {
        try {
            await fetch('/api/alert/stop', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    alert_session_id: appState.activeAlert.sessionId,
                    reason: reason
                })
            });
        } catch (error) {
            console.error('Failed to stop alert on server:', error);
        }
    }

    resetAlertState();
}

/**
 * Reset alert state back to IDLE.
 */
function resetAlertState() {
    appState.activeAlert.sessionId = null;
    appState.activeAlert.destinationId = null;
    appState.activeAlert.destinationName = '';
    appState.activeAlert.currentEta = null;
    appState.activeAlert.lastUpdated = null;
    appState.activeAlert.state = 'IDLE';
    appState.trackingMode = false;
    updateUIForState('IDLE');
}

/**
 * Request browser geolocation permission.
 * Returns true if granted, false if denied.
 */
function requestLocationPermission() {
    return new Promise((resolve) => {
        if (!navigator.geolocation) {
            showError('Geolocation is not supported by your browser.');
            resolve(false);
            return;
        }

        navigator.geolocation.getCurrentPosition(
            () => resolve(true),   // Permission granted
            (error) => {
                if (error.code === error.PERMISSION_DENIED) {
                    showError('Location permission denied. PingPlace needs your location to calculate ETA. Please enable location in your browser settings.');
                } else {
                    showError('Unable to get your location. Please try again.');
                }
                resolve(false);
            },
            { timeout: 10000 }
        );
    });
}

/**
 * Update the UI based on the current alert state.
 * Shows/hides buttons and changes status indicator.
 */
function updateUIForState(state) {
    const startBtn = document.getElementById('btn-start-alert');
    const stopBtn = document.getElementById('btn-stop-alert');
    const trackBtn = document.getElementById('btn-track-only');
    const dismissBtn = document.getElementById('btn-dismiss-alert');
    const etaDisplay = document.querySelector('.eta-display');
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');
    const destSelect = document.getElementById('destination-select');
    const transportBtns = document.querySelectorAll('.transport-btn');

    switch (state) {
        case 'IDLE':
            startBtn.style.display = 'block';
            stopBtn.style.display = 'none';
            trackBtn.style.display = 'block';
            dismissBtn.style.display = 'none';
            etaDisplay.style.display = 'none';
            statusDot.className = 'status-dot idle';
            statusText.textContent = 'No alert active';
            destSelect.disabled = false;
            transportBtns.forEach(b => b.disabled = false);
            break;

        case 'POLLING': {
            const modeEmoji = { car: '🚗', bus: '🚌', train: '🚆' }[appState.travelMode] || '';
            startBtn.style.display = 'none';
            stopBtn.style.display = 'block';
            trackBtn.style.display = 'none';
            dismissBtn.style.display = 'none';
            etaDisplay.style.display = 'block';
            statusDot.className = 'status-dot polling';
            statusText.textContent = appState.trackingMode
                ? `${modeEmoji} Tracking: ${appState.activeAlert.destinationName}`
                : `${modeEmoji} Alert active: ${appState.activeAlert.destinationName}`;
            destSelect.disabled = true;
            transportBtns.forEach(b => b.disabled = true);
            break;
        }

        case 'FIRED':
            startBtn.style.display = 'none';
            stopBtn.style.display = 'none';
            trackBtn.style.display = 'none';
            dismissBtn.style.display = 'block';
            statusDot.className = 'status-dot fired';
            statusText.textContent = 'ALERT! Approaching destination!';
            destSelect.disabled = true;
            transportBtns.forEach(b => b.disabled = true);
            break;
    }
}

/**
 * Update the ETA display on the dashboard.
 * Shows travel time and, for car/bus, any traffic delay.
 */
function updateEtaDisplay(etaMinutes, etaText, trafficDelay) {
    const etaValue = document.querySelector('.eta-value');
    const etaLabel = document.querySelector('.eta-label');
    const etaUpdated = document.querySelector('.eta-updated');

    etaValue.textContent = etaMinutes !== null ? etaMinutes : '--';

    // Show traffic delay hint for car/bus
    if (trafficDelay && trafficDelay > 0 && appState.travelMode !== 'train') {
        etaLabel.innerHTML = `min to destination &nbsp;<span style="color:#ef4444;font-size:0.75rem;font-weight:600">+${trafficDelay} min traffic</span>`;
    } else {
        etaLabel.textContent = 'min to destination';
    }

    etaUpdated.textContent = `Updated ${new Date().toLocaleTimeString()}`;
    appState.activeAlert.currentEta = etaMinutes;
    appState.activeAlert.lastUpdated = new Date();
}

/**
 * Show the full-screen alert overlay.
 */
function showAlertOverlay(destinationName, etaMinutes) {
    const overlay = document.getElementById('alert-overlay');
    const message = document.querySelector('.alert-message');
    message.textContent = `You're ${etaMinutes} min from ${destinationName}!`;
    overlay.style.display = 'flex';
}

/**
 * Hide the alert overlay.
 */
function hideAlertOverlay() {
    document.getElementById('alert-overlay').style.display = 'none';
}

/**
 * Show an error message in the UI.
 */
function showError(message) {
    const el = document.getElementById('error-message');
    el.textContent = message;
    el.style.display = 'block';
}

/**
 * Hide the error message.
 */
function hideError() {
    document.getElementById('error-message').style.display = 'none';
}

/**
 * Update the destination select dropdown from appState.destinations.
 */
function updateDestinationSelect() {
    const select = document.getElementById('destination-select');
    // Keep the first "Select destination..." option
    select.innerHTML = '<option value="">Select destination...</option>';

    appState.destinations.forEach(dest => {
        const option = document.createElement('option');
        option.value = dest.id;
        option.textContent = `${dest.name} (${dest.alert_threshold_minutes} min)`;
        select.appendChild(option);
    });
}

// Start the app when the page loads
document.addEventListener('DOMContentLoaded', initApp);
