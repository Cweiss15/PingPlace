/**
 * static/js/polling.js — Adaptive ETA Polling Loop
 *
 * This is the CORE of PingPlace's real-time behavior.
 *
 * HOW POLLING WORKS:
 * - We repeatedly ask the server "how far am I from my destination?"
 * - The server uses Google Distance Matrix API (with traffic) to calculate
 * - We adjust HOW OFTEN we ask based on how far away we are:
 *     - Far away (>30 min): Check every 60 seconds (save API calls)
 *     - Getting closer (10-30 min): Check every 30 seconds
 *     - Almost there (<10 min): Check every 15 seconds (need accuracy)
 *
 * This is called "adaptive polling" — the interval adapts to the situation.
 *
 * WHY NOT WEBSOCKETS?
 * For a student project with free-tier hosting, simple polling is:
 * 1. Easier to understand and debug
 * 2. Works with free Render hosting (no WebSocket support needed)
 * 3. Sufficient for our use case (15-60 second updates are fine for commuting)
 */

// The timeout ID so we can cancel the next scheduled poll
let pollingTimeoutId = null;

/**
 * Calculate how many milliseconds to wait before the next poll.
 * This is the "adaptive" part — shorter intervals when close.
 *
 * @param {number|null} etaMinutes - Current ETA in minutes
 * @returns {number} Milliseconds until next poll
 */
function getPollingInterval(etaMinutes) {
    if (etaMinutes === null) return 30000;  // Unknown ETA: check every 30s

    if (etaMinutes > 30) return 60000;      // Far: every 60 seconds
    if (etaMinutes > 10) return 30000;      // Medium: every 30 seconds
    return 15000;                            // Close: every 15 seconds
}

/**
 * Start the polling loop.
 * Called when user clicks "Start Alert" or "Track Only".
 */
function startPolling() {
    // Cancel any existing poll
    stopPolling();

    // Execute first poll immediately, then schedule next
    executePollCycle();
}

/**
 * Stop the polling loop.
 * Called when user clicks "Stop" or alert fires.
 */
function stopPolling() {
    if (pollingTimeoutId) {
        clearTimeout(pollingTimeoutId);
        pollingTimeoutId = null;
    }
}

/**
 * Execute one poll cycle:
 * 1. Get user's current GPS position
 * 2. Send it to server to calculate ETA
 * 3. Check if ETA <= threshold (fire alert if so)
 * 4. Schedule the next poll
 */
async function executePollCycle() {
    // Don't poll if alert already fired or state is idle
    if (appState.activeAlert.state !== 'POLLING') return;

    try {
        // Step 1: Get current GPS position
        const position = await getCurrentPosition();
        if (!position) {
            // Can't get location, try again later
            scheduleNextPoll(appState.activeAlert.currentEta);
            return;
        }

        const userLat = position.coords.latitude;
        const userLng = position.coords.longitude;

        // Update map with new position
        updateMapUserPosition(userLat, userLng);

        // Step 2: Ask server for ETA
        const etaResponse = await fetch('/api/eta', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                destination_id: appState.activeAlert.destinationId,
                latitude: userLat,
                longitude: userLng
            })
        });

        if (!etaResponse.ok) {
            console.error('ETA request failed:', etaResponse.status);
            scheduleNextPoll(appState.activeAlert.currentEta);
            return;
        }

        const etaData = await etaResponse.json();

        // Step 3: Update UI with new ETA
        updateEtaDisplay(etaData.eta_minutes);

        // Step 4: Check if we should fire the alert
        if (etaData.should_alert && !appState.trackingMode) {
            // ETA is within threshold! Fire the alert!
            fireAlert();
            return;  // Don't schedule next poll — alert has fired
        }

        // Step 5: Schedule next poll with adaptive interval
        scheduleNextPoll(etaData.eta_minutes);

    } catch (error) {
        console.error('Poll cycle error:', error);
        // On error, retry after 30 seconds
        scheduleNextPoll(null);
    }
}

/**
 * Schedule the next poll using adaptive interval.
 *
 * @param {number|null} currentEta - Current ETA for interval calculation
 */
function scheduleNextPoll(currentEta) {
    const interval = getPollingInterval(currentEta);
    pollingTimeoutId = setTimeout(executePollCycle, interval);
}

/**
 * Get current GPS position as a Promise.
 * Wraps the callback-based Geolocation API.
 *
 * @returns {Promise<GeolocationPosition|null>}
 */
function getCurrentPosition() {
    return new Promise((resolve) => {
        navigator.geolocation.getCurrentPosition(
            (position) => resolve(position),
            (error) => {
                console.warn('Geolocation error:', error.message);
                resolve(null);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 5000  // Accept position up to 5 seconds old
            }
        );
    });
}
