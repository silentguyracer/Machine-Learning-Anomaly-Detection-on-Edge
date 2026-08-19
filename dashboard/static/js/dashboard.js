// WebSocket connection
const WS_URL = `ws://${window.location.host}/ws`;
let ws = null;
let reconnectTimer = null;

// Device state registry
const devices = {};  

function connectWebSocket() {
    ws = new WebSocket(WS_URL);
    
    ws.onopen = () => {
        updateConnectionStatus('connected');
        clearTimeout(reconnectTimer);
    };
    
    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleMessage(msg);
        } catch(e) {
            console.error("Error parsing WS message", e);
        }
    };
    
    ws.onclose = () => {
        updateConnectionStatus('disconnected');
        // Auto-reconnect after 3 seconds
        reconnectTimer = setTimeout(connectWebSocket, 3000);
    };
    
    ws.onerror = () => {
        updateConnectionStatus('error');
    };
}

function handleMessage(msg) {
    switch (msg.type) {
        case 'initial_state': 
            handleInitialState(msg); 
            break;
        case 'sensor_update': 
            handleSensorUpdate(msg); 
            break;
        case 'system_stats':  
            handleSystemStats(msg); 
            break;
        case 'alert':         
            handleAlert(msg); 
            break;
        case 'device_status_update':
            handleDeviceStatusUpdate(msg);
            break;
    }
}

function handleInitialState(msg) {
    if (msg.devices && Array.isArray(msg.devices)) {
        msg.devices.forEach(device => {
            if (!devices[device.id]) {
                createDeviceCard(device);
                devices[device.id] = device;
                initDeviceCharts(device.id);
            }
        });
    }
    if (msg.recent_alerts && Array.isArray(msg.recent_alerts)) {
        // Clear and add in reverse so oldest is at bottom
        clearAlerts();
        [...msg.recent_alerts].reverse().forEach(alert => addAlert(alert));
    }
}

function createDeviceCard(device) {
    const grid = document.getElementById('device-grid');
    if (!grid) return;
    
    const cardHtml = `
        <div class="device-card ${device.status === 'offline' ? 'device-offline' : ''}" id="card-${device.id}" data-device-id="${device.id}">
            <div class="card-header">
                <div class="device-name">${device.name}</div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <label class="switch">
                        <input type="checkbox" id="status-toggle-${device.id}" ${device.status === 'online' ? 'checked' : ''} onchange="toggleDeviceConnection('${device.id}')">
                        <span class="slider-round"></span>
                    </label>
                    <div class="status-badge ${device.status === 'online' ? 'online' : 'offline'}" id="status-badge-${device.id}">
                        <span class="pulse-dot"></span><span class="status-badge-text">${(device.status || 'OFFLINE').toUpperCase()}</span>
                    </div>
                </div>
            </div>
            
            <div class="anomaly-gauge-container">
                <svg class="gauge" id="gauge-${device.id}" viewBox="0 0 120 70">
                    <path class="gauge-bg" d="M 20 60 A 40 40 0 0 1 100 60" />
                    <path class="gauge-fill" d="M 20 60 A 40 40 0 0 1 100 60" style="stroke-dasharray: 125.66; stroke-dashoffset: 125.66;" />
                    <text class="gauge-text" x="60" y="55">0</text>
                    <text class="gauge-label" x="60" y="68">Score</text>
                </svg>
            </div>
            
            <div class="sensor-values" id="values-${device.id}">
                <div class="sensor-val-box">
                    <div class="sensor-val-header"><span>Temp</span><span style="color:var(--color-temp)">●</span></div>
                    <div class="sensor-val-reading"><span id="val-${device.id}-temperature">--</span> <span class="sensor-unit">°C</span></div>
                </div>
                <div class="sensor-val-box">
                    <div class="sensor-val-header"><span>Vib</span><span style="color:var(--color-vib)">●</span></div>
                    <div class="sensor-val-reading"><span id="val-${device.id}-vibration">--</span> <span class="sensor-unit">g</span></div>
                </div>
                <div class="sensor-val-box">
                    <div class="sensor-val-header"><span>Curr</span><span style="color:var(--color-curr)">●</span></div>
                    <div class="sensor-val-reading"><span id="val-${device.id}-current">--</span> <span class="sensor-unit">A</span></div>
                </div>
                <div class="sensor-val-box">
                    <div class="sensor-val-header"><span>Press</span><span style="color:var(--color-press)">●</span></div>
                    <div class="sensor-val-reading"><span id="val-${device.id}-pressure">--</span> <span class="sensor-unit">bar</span></div>
                </div>
            </div>
            
            <div class="chart-grid" id="charts-${device.id}">
                <div class="mini-chart"><canvas id="chart-${device.id}-temperature"></canvas></div>
                <div class="mini-chart"><canvas id="chart-${device.id}-vibration"></canvas></div>
                <div class="mini-chart"><canvas id="chart-${device.id}-current"></canvas></div>
                <div class="mini-chart"><canvas id="chart-${device.id}-pressure"></canvas></div>
            </div>
            
            <div class="remedy-action-container" id="remedy-container-${device.id}"></div>

            <div class="model-verdicts" id="verdicts-${device.id}">
                <span class="verdict-badge" id="verdict-${device.id}-isolation_forest">IF</span>
                <span class="verdict-badge" id="verdict-${device.id}-lof">LOF</span>
                <span class="verdict-badge" id="verdict-${device.id}-statistical">STAT</span>
                <button class="inject-trigger-btn" onclick="toggleInjectPanel(event, '${device.id}')">⚡ Inject</button>
            </div>
            
            <div class="inject-panel" id="inject-panel-${device.id}" style="display: none;" onclick="event.stopPropagation()">
                <div class="inject-header">Simulate Sensor Fault</div>
                <div class="inject-row">
                    <label>Anomaly Type</label>
                    <select id="inject-type-${device.id}">
                        <option value="spike">Spike (Transient Peak)</option>
                        <option value="drift">Drift (Sensor Degrade)</option>
                        <option value="oscillation">Oscillation (Unstable Sine)</option>
                        <option value="flatline">Flatline (Sensor Dead)</option>
                    </select>
                </div>
                <div class="inject-row">
                    <label>Target Sensors</label>
                    <div class="inject-checkboxes">
                        <label><input type="checkbox" id="sensor-${device.id}-temperature" checked> Temp</label>
                        <label><input type="checkbox" id="sensor-${device.id}-vibration"> Vib</label>
                        <label><input type="checkbox" id="sensor-${device.id}-current"> Curr</label>
                        <label><input type="checkbox" id="sensor-${device.id}-pressure"> Press</label>
                    </div>
                </div>
                <button class="inject-submit-btn" onclick="submitAnomaly('${device.id}')">Inject Fault</button>
            </div>
        </div>
    `;
    
    grid.insertAdjacentHTML('beforeend', cardHtml);
}

function handleSensorUpdate(msg) {
    const devId = msg.device_id;
    
    // If device doesn't exist yet, create it dynamically
    if (!devices[devId]) {
        const newDev = { id: devId, name: msg.device_name, status: 'online' };
        createDeviceCard(newDev);
        devices[devId] = newDev;
        initDeviceCharts(devId);
    }
    
    // Update text values
    if (msg.sensors) {
        for (const [key, val] of Object.entries(msg.sensors)) {
            const el = document.getElementById(`val-${devId}-${key}`);
            if (el) {
                // Formatting for display
                el.textContent = (typeof val === 'number') ? val.toFixed(1) : val;
            }
        }
        
        // Update charts
        updateDeviceCharts(devId, msg.sensors, msg.is_anomaly, msg.anomalous_sensors);
    }
    
    // Update gauge
    if (msg.anomaly_score !== undefined) {
        updateGauge(devId, msg.anomaly_score);
    }
    
    // Update model verdicts
    if (msg.model_verdicts) {
        for (const [model, isAnom] of Object.entries(msg.model_verdicts)) {
            const el = document.getElementById(`verdict-${devId}-${model}`);
            if (el) {
                if (isAnom) el.classList.add('active');
                else el.classList.remove('active');
            }
        }
    }
    
    // Toggle overall anomaly state UI
    toggleAnomalyState(devId, msg.is_anomaly, msg.severity, msg.anomalous_sensors);
}

function handleSystemStats(msg) {
    if (msg.total_readings !== undefined) document.getElementById('stat-total-readings').textContent = msg.total_readings.toLocaleString();
    if (msg.total_anomalies !== undefined) document.getElementById('stat-total-anomalies').textContent = msg.total_anomalies.toLocaleString();
    if (msg.anomaly_rate !== undefined) document.getElementById('stat-anomaly-rate').textContent = msg.anomaly_rate.toFixed(2) + '%';
    if (msg.active_devices !== undefined) document.getElementById('stat-active-devices').textContent = msg.active_devices;
    if (msg.uptime_seconds !== undefined) document.getElementById('stat-uptime').textContent = formatUptime(msg.uptime_seconds);
}

function handleAlert(msg) {
    addAlert(msg);
}

function updateConnectionStatus(status) {
    const el = document.getElementById('connection-status');
    const textEl = el.querySelector('.status-text');
    
    el.className = 'connection-status'; // reset
    if (status === 'connected') {
        el.classList.add('status-connected');
        textEl.textContent = 'LIVE';
    } else if (status === 'disconnected') {
        el.classList.add('status-offline');
        textEl.textContent = 'OFFLINE';
    } else {
        el.classList.add('status-error');
        textEl.textContent = 'ERROR';
    }
}

function toggleAnomalyState(deviceId, isAnomaly, severity, anomalousSensors) {
    const card = document.getElementById(`card-${deviceId}`);
    if (!card) return;
    
    // Remove old severity classes
    card.classList.remove('anomaly-LOW', 'anomaly-MEDIUM', 'anomaly-HIGH', 'anomaly-CRITICAL');
    
    const container = document.getElementById(`remedy-container-${deviceId}`);
    if (isAnomaly) {
        card.classList.add(`anomaly-${severity.toUpperCase()}`);
        
        // Show remediation action recommendation based on anomalous sensor
        let remedyText = "General System Calibration";
        if (anomalousSensors && anomalousSensors.length > 0) {
            const primarySensor = anomalousSensors[0];
            if (primarySensor === 'temperature') remedyText = "Adjust Coolant Flow";
            else if (primarySensor === 'vibration') remedyText = "Calibrate Dynamic Balance";
            else if (primarySensor === 'current') remedyText = "Stabilize Voltage Supply";
            else if (primarySensor === 'pressure') remedyText = "Release Pressure Valve";
        }
        
        container.innerHTML = `
            <div class="remedy-box">
                <span class="remedy-recommendation">🔧 Recommended: ${remedyText}</span>
                <button class="remedy-btn" onclick="executeRemedy('${deviceId}', this)">Resolve</button>
            </div>
        `;
    } else {
        container.innerHTML = "";
    }
}

// Update clock every second
function updateClock() {
    const timeEl = document.getElementById('current-time');
    if (timeEl) {
        timeEl.textContent = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
}

function formatUptime(seconds) {
    const h = Math.floor(seconds/3600);
    const m = Math.floor((seconds%3600)/60);
    const s = Math.floor(seconds%60);
    return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}

// Init on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket();
    setInterval(updateClock, 1000);
    updateClock();
    fetchCurrentConfig();
});

function toggleInjectPanel(event, deviceId) {
    if (event) event.stopPropagation();
    const panel = document.getElementById(`inject-panel-${deviceId}`);
    if (panel) {
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    }
}

async function submitAnomaly(deviceId) {
    const typeSelect = document.getElementById(`inject-type-${deviceId}`);
    const anomalyType = typeSelect.value;
    
    const sensors = [];
    if (document.getElementById(`sensor-${deviceId}-temperature`).checked) sensors.push("temperature");
    if (document.getElementById(`sensor-${deviceId}-vibration`).checked) sensors.push("vibration");
    if (document.getElementById(`sensor-${deviceId}-current`).checked) sensors.push("current");
    if (document.getElementById(`sensor-${deviceId}-pressure`).checked) sensors.push("pressure");
    
    try {
        const response = await fetch(`/api/devices/${deviceId}/trigger_anomaly`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                anomaly_type: anomalyType,
                affected_sensors: sensors
            })
        });
        
        const result = await response.json();
        if (response.ok) {
            const btn = document.querySelector(`#inject-panel-${deviceId} .inject-submit-btn`);
            const origText = btn.textContent;
            btn.textContent = "Fault Injected!";
            btn.style.backgroundColor = "var(--sev-normal)";
            setTimeout(() => {
                btn.textContent = origText;
                btn.style.backgroundColor = "";
                toggleInjectPanel(null, deviceId);
            }, 1500);
        } else {
            alert("Error: " + result.detail);
        }
    } catch (e) {
        console.error("Failed to inject anomaly", e);
        alert("Failed to connect to edge server to inject anomaly");
    }
}

// Config Panel Helpers
async function fetchCurrentConfig() {
    try {
        const response = await fetch('/api/config');
        if (!response.ok) return;
        const config = await response.json();
        
        // Update sliders & display labels
        document.getElementById('slider-anomaly-threshold').value = config.anomaly_threshold;
        document.getElementById('val-anomaly-threshold').textContent = config.anomaly_threshold.toFixed(2);
        
        document.getElementById('slider-z-threshold').value = config.z_threshold;
        document.getElementById('val-z-threshold').textContent = config.z_threshold.toFixed(1);
        
        document.getElementById('slider-w-iso').value = Math.round(config.w_iso * 100);
        document.getElementById('val-w-iso').textContent = Math.round(config.w_iso * 100) + '%';
        
        document.getElementById('slider-w-lof').value = Math.round(config.w_lof * 100);
        document.getElementById('val-w-lof').textContent = Math.round(config.w_lof * 100) + '%';
        
        document.getElementById('slider-w-stat').value = Math.round(config.w_stat * 100);
        document.getElementById('val-w-stat').textContent = Math.round(config.w_stat * 100) + '%';
        
        document.getElementById('slider-w-range').value = Math.round(config.w_range * 100);
        document.getElementById('val-w-range').textContent = Math.round(config.w_range * 100) + '%';
    } catch (e) {
        console.error("Failed to fetch model configuration", e);
    }
}

function updateConfigValue(type, val) {
    const displayEl = document.getElementById(`val-${type}`);
    if (!displayEl) return;
    
    if (type === 'anomaly-threshold') {
        displayEl.textContent = parseFloat(val).toFixed(2);
    } else if (type === 'z-threshold') {
        displayEl.textContent = parseFloat(val).toFixed(1);
    } else {
        displayEl.textContent = val + '%';
    }
}

async function applyModelConfig() {
    const anomalyThreshold = parseFloat(document.getElementById('slider-anomaly-threshold').value);
    const zThreshold = parseFloat(document.getElementById('slider-z-threshold').value);
    
    // Parse weight percentages to decimals
    const wIso = parseInt(document.getElementById('slider-w-iso').value) / 100;
    const wLof = parseInt(document.getElementById('slider-w-lof').value) / 100;
    const wStat = parseInt(document.getElementById('slider-w-stat').value) / 100;
    const wRange = parseInt(document.getElementById('slider-w-range').value) / 100;
    
    const applyBtn = document.querySelector('.config-apply-btn');
    const origText = applyBtn.textContent;
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                w_iso: wIso,
                w_lof: wLof,
                w_stat: wStat,
                w_range: wRange,
                anomaly_threshold: anomalyThreshold,
                z_threshold: zThreshold
            })
        });
        
        const result = await response.json();
        if (response.ok) {
            applyBtn.textContent = "Settings Applied!";
            applyBtn.style.backgroundColor = "var(--sev-normal)";
            
            // Re-read back from the response (which normalizes weights if they didn't sum to 1.0)
            const updated = result.config;
            document.getElementById('slider-w-iso').value = Math.round(updated.w_iso * 100);
            document.getElementById('val-w-iso').textContent = Math.round(updated.w_iso * 100) + '%';
            
            document.getElementById('slider-w-lof').value = Math.round(updated.w_lof * 100);
            document.getElementById('val-w-lof').textContent = Math.round(updated.w_lof * 100) + '%';
            
            document.getElementById('slider-w-stat').value = Math.round(updated.w_stat * 100);
            document.getElementById('val-w-stat').textContent = Math.round(updated.w_stat * 100) + '%';
            
            document.getElementById('slider-w-range').value = Math.round(updated.w_range * 100);
            document.getElementById('val-w-range').textContent = Math.round(updated.w_range * 100) + '%';
            
            setTimeout(() => {
                applyBtn.textContent = origText;
                applyBtn.style.backgroundColor = "";
            }, 2000);
        } else {
            alert("Failed to apply settings: " + result.detail);
        }
    } catch (e) {
        console.error("Error setting model configuration", e);
        alert("Failed to connect to edge server to save configuration");
    }
}

async function executeRemedy(deviceId, btn) {
    if (!btn) return;
    const origText = btn.textContent;
    btn.textContent = "Resolving...";
    btn.disabled = true;
    btn.style.opacity = "0.7";
    
    try {
        const response = await fetch(`/api/devices/${deviceId}/resolve_anomaly`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const result = await response.json();
        if (response.ok) {
            btn.textContent = "Remedied!";
            btn.style.backgroundColor = "var(--sev-normal)";
            
            // Clean up visual box shortly
            setTimeout(() => {
                const container = document.getElementById(`remedy-container-${deviceId}`);
                if (container) container.innerHTML = "";
                const card = document.getElementById(`card-${deviceId}`);
                if (card) {
                    card.classList.remove('anomaly-LOW', 'anomaly-MEDIUM', 'anomaly-HIGH', 'anomaly-CRITICAL');
                }
            }, 1500);
        } else {
            alert("Error: " + result.detail);
            btn.textContent = origText;
            btn.disabled = false;
            btn.style.opacity = "";
        }
    } catch (e) {
        console.error("Failed to execute self-healing", e);
        alert("Failed to connect to edge server to execute self-healing action");
        btn.textContent = origText;
        btn.disabled = false;
        btn.style.opacity = "";
    }
}

function handleDeviceStatusUpdate(msg) {
    const devId = msg.device_id;
    const status = msg.status;
    
    // Update local state registry
    if (devices[devId]) {
        devices[devId].status = status;
    }
    
    // Update UI elements
    const checkbox = document.getElementById(`status-toggle-${devId}`);
    if (checkbox) {
        checkbox.checked = (status === 'online');
    }
    
    const badge = document.getElementById(`status-badge-${devId}`);
    const badgeText = badge ? badge.querySelector('.status-badge-text') : null;
    const card = document.getElementById(`card-${devId}`);
    
    if (badge && badgeText) {
        badge.className = `status-badge ${status}`;
        badgeText.textContent = status.toUpperCase();
    }
    
    if (card) {
        if (status === 'offline') {
            card.classList.add('device-offline');
        } else {
            card.classList.remove('device-offline');
        }
    }
}

async function toggleDeviceConnection(deviceId) {
    try {
        const response = await fetch(`/api/devices/${deviceId}/toggle`, {
            method: 'POST'
        });
        const result = await response.json();
        if (!response.ok) {
            alert("Error toggling device state: " + result.detail);
            // Revert checkbox state
            const checkbox = document.getElementById(`status-toggle-${deviceId}`);
            if (checkbox) checkbox.checked = !checkbox.checked;
        }
    } catch (e) {
        console.error("Failed to toggle device connection", e);
        alert("Failed to connect to edge server to toggle device connection");
        // Revert checkbox state
        const checkbox = document.getElementById(`status-toggle-${deviceId}`);
        if (checkbox) checkbox.checked = !checkbox.checked;
    }
}

async function retrainModels() {
    const btn = document.querySelector('.retrain-btn');
    const statusEl = document.getElementById('retrain-status-text');
    if (!btn || !statusEl) return;
    
    const origText = btn.textContent;
    btn.textContent = "Retraining in progress...";
    btn.disabled = true;
    btn.style.opacity = "0.7";
    statusEl.textContent = "Processing SQLite historical logs...";
    statusEl.style.color = "var(--accent-blue)";
    
    try {
        const response = await fetch('/api/models/retrain', {
            method: 'POST'
        });
        const result = await response.json();
        if (response.ok) {
            btn.textContent = "Success!";
            btn.style.backgroundColor = "var(--sev-normal)";
            statusEl.textContent = `Retrained on ${result.stats.sample_count} samples! Contamination: ${Math.round(result.stats.contamination * 100)}%`;
            statusEl.style.color = "var(--sev-normal)";
            
            setTimeout(() => {
                btn.textContent = origText;
                btn.disabled = false;
                btn.style.opacity = "";
                btn.style.backgroundColor = "";
            }, 3000);
        } else {
            statusEl.textContent = `Error: ${result.detail}`;
            statusEl.style.color = "var(--sev-high)";
            btn.textContent = "Failed";
            btn.style.backgroundColor = "var(--sev-high)";
            
            setTimeout(() => {
                btn.textContent = origText;
                btn.disabled = false;
                btn.style.opacity = "";
                btn.style.backgroundColor = "";
            }, 3000);
        }
    } catch (e) {
        console.error("Failed to retrain models", e);
        statusEl.textContent = "Error: Connection lost to edge server";
        statusEl.style.color = "var(--sev-high)";
        btn.textContent = origText;
        btn.disabled = false;
        btn.style.opacity = "";
    }
}
