/**
 * static/js/alert.js — Notification & Sound Alert System
 *
 * When the ETA drops below the threshold, we need to WAKE UP the user.
 * We use three methods simultaneously:
 *
 * 1. BROWSER NOTIFICATION (Push notification) — works even if tab is minimized
 * 2. WEB AUDIO (Alarm sound) — plays an oscillating tone through speakers
 * 3. VISUAL OVERLAY — full-screen overlay with big text (can't miss it)
 *
 * WHY ALL THREE?
 * - Notification: User might have phone in pocket, this vibrates/shows banner
 * - Audio: If they're wearing earbuds (commuter on bus/train), they'll hear it
 * - Visual: If they're looking at the screen, impossible to miss
 */

// Web Audio context (created lazily to avoid browser autoplay restrictions)
let audioContext = null;
let oscillatorNode = null;
let isAlarmPlaying = false;

/**
 * Fire the alert! Called when ETA <= threshold.
 * This is the big moment — the whole point of the app.
 */
function fireAlert() {
    // Update state
    appState.activeAlert.state = 'FIRED';
    updateUIForState('FIRED');

    // Stop polling (no need to keep checking)
    stopPolling();

    // 1. Show visual overlay
    showAlertOverlay(
        appState.activeAlert.destinationName,
        appState.activeAlert.currentEta
    );

    // 2. Send browser notification
    sendNotification(
        'PingPlace Alert!',
        `You're ${appState.activeAlert.currentEta} min from ${appState.activeAlert.destinationName}!`
    );

    // 3. Play alarm sound
    playAlertSound();
}

/**
 * Request notification permission and send a notification.
 *
 * The Notification API requires explicit user permission. We request it
 * here (browser shows a popup asking "Allow notifications?").
 *
 * @param {string} title - Notification title
 * @param {string} body - Notification body text
 */
function sendNotification(title, body) {
    // Check if browser supports notifications
    if (!('Notification' in window)) {
        console.log('Notifications not supported');
        return;
    }

    if (Notification.permission === 'granted') {
        // Already have permission, send immediately
        new Notification(title, { body, icon: '📍' });
    } else if (Notification.permission !== 'denied') {
        // Ask for permission, then send
        Notification.requestPermission().then(permission => {
            if (permission === 'granted') {
                new Notification(title, { body, icon: '📍' });
            }
        });
    }
    // If 'denied', we can't do anything — user blocked notifications
}

/**
 * Play an alarm sound using the Web Audio API.
 *
 * The Web Audio API lets us generate sound programmatically — no audio
 * files needed! We create an "oscillator" (like a tuning fork) that
 * alternates between two frequencies to create an alarm-like beeping.
 *
 * HOW OSCILLATORS WORK:
 * An oscillator generates a waveform at a specific frequency (Hz).
 * - 440 Hz = A4 note (concert pitch)
 * - 880 Hz = A5 note (one octave higher)
 * We switch between them to create a classic alarm "bee-boo-bee-boo" sound.
 */
function playAlertSound() {
    if (isAlarmPlaying) return;

    try {
        // Create AudioContext (browser's audio engine)
        // Must be created in response to user interaction OR after user gesture
        audioContext = new (window.AudioContext || window.webkitAudioContext)();

        // Create oscillator — this is the "instrument" that makes sound
        oscillatorNode = audioContext.createOscillator();
        oscillatorNode.type = 'square';  // Square wave = harsh/alarm-like sound
        oscillatorNode.frequency.setValueAtTime(440, audioContext.currentTime);

        // Create gain node (volume control) so we can set a reasonable volume
        const gainNode = audioContext.createGain();
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);  // 30% volume

        // Connect: oscillator → gain → speakers
        oscillatorNode.connect(gainNode);
        gainNode.connect(audioContext.destination);

        // Start the oscillator (starts making sound)
        oscillatorNode.start();
        isAlarmPlaying = true;

        // Alternate frequency every 500ms for alarm effect
        let isHigh = false;
        const frequencyInterval = setInterval(() => {
            if (!isAlarmPlaying) {
                clearInterval(frequencyInterval);
                return;
            }
            isHigh = !isHigh;
            oscillatorNode.frequency.setValueAtTime(
                isHigh ? 880 : 440,
                audioContext.currentTime
            );
        }, 500);

    } catch (error) {
        console.error('Failed to play alert sound:', error);
    }
}

/**
 * Stop the alarm sound.
 * Called when user dismisses the alert.
 */
function stopAlertSound() {
    if (!isAlarmPlaying) return;

    try {
        if (oscillatorNode) {
            oscillatorNode.stop();
            oscillatorNode.disconnect();
            oscillatorNode = null;
        }
        if (audioContext) {
            audioContext.close();
            audioContext = null;
        }
    } catch (error) {
        // Ignore errors during cleanup
    }

    isAlarmPlaying = false;
}

/**
 * Request notification permission proactively.
 * Called early so the browser prompt appears before the alert fires.
 * (If we only ask during the alert, user might miss it.)
 */
function requestNotificationPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
}

// Request notification permission when page loads
document.addEventListener('DOMContentLoaded', requestNotificationPermission);
