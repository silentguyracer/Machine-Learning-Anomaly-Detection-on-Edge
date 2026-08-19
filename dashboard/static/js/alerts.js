const MAX_ALERTS = 50;
let totalAlertsReceived = 0;

function addAlert(alertData) {
    const feed = document.getElementById('alerts-feed');
    if (!feed) return;
    
    // Remove oldest if exceeding max
    while (feed.children.length >= MAX_ALERTS) {
        feed.removeChild(feed.lastChild);
    }
    
    const alertId = alertData.id || `alert-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
    const severityClass = getSeverityClass(alertData.severity);
    const timeStr = formatTime(alertData.timestamp);
    const scoreFormatted = (alertData.anomaly_score * 100).toFixed(1);
    
    const alertHtml = `
        <div class="alert-item ${severityClass}" id="${alertId}">
            <div class="alert-severity-bar"></div>
            <div class="alert-content">
                <div class="alert-header">
                    <span class="alert-device">${alertData.device_name || alertData.device_id}</span>
                    <span class="alert-badge ${alertData.severity}">${alertData.severity}</span>
                </div>
                <div class="alert-message">${alertData.message}</div>
                <div class="alert-meta">
                    <span class="alert-score">Score: ${scoreFormatted}%</span>
                    <span class="alert-time">${timeStr}</span>
                </div>
            </div>
        </div>
    `;
    
    // Insert at top
    feed.insertAdjacentHTML('afterbegin', alertHtml);
    
    // Update counter
    totalAlertsReceived++;
    const counterEl = document.getElementById('alert-counter');
    if (counterEl) {
        counterEl.textContent = totalAlertsReceived;
        // Small flash animation
        counterEl.style.transform = 'scale(1.2)';
        setTimeout(() => { counterEl.style.transform = 'scale(1)'; }, 200);
    }
}

function formatTime(isoString) {
    try {
        const date = isoString ? new Date(isoString) : new Date();
        return date.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (e) {
        return '--:--:--';
    }
}

function getSeverityClass(severity) {
    if (!severity) return 'severity-LOW';
    return `severity-${severity.toUpperCase()}`;
}

function clearAlerts() {
    const feed = document.getElementById('alerts-feed');
    if (feed) {
        feed.innerHTML = '';
    }
    totalAlertsReceived = 0;
    const counterEl = document.getElementById('alert-counter');
    if (counterEl) counterEl.textContent = '0';
}

function exportAlerts() {
    window.location.href = '/api/alerts/export';
}
