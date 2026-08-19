// Global chart registry: {"EDGE-001-temperature": Chart instance, ...}
const chartRegistry = {};

// Sensor config mapping CSS vars to Chart.js
const SENSOR_CONFIG = {
  temperature: { label: 'Temp', color: '#f97316', min: 20, max: 120, unit: '°C' },
  vibration:   { label: 'Vib', color: '#a78bfa', min: 0, max: 1.0, unit: 'g' },
  current:     { label: 'Curr', color: '#22c55e', min: 0, max: 10, unit: 'A' },
  pressure:    { label: 'Press', color: '#38bdf8', min: 0, max: 5, unit: 'bar' },
};

const MAX_CHART_POINTS = 30; // Reduce points for edge mini-charts

Chart.defaults.color = '#94a3b8';
Chart.defaults.font.family = "'Inter', sans-serif";

function initDeviceCharts(deviceId) {
    const sensors = ['temperature', 'vibration', 'current', 'pressure'];
    
    sensors.forEach(sensor => {
        const canvasId = `chart-${deviceId}-${sensor}`;
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        const config = SENSOR_CONFIG[sensor];
        
        // Create gradient fill
        const gradient = ctx.createLinearGradient(0, 0, 0, 60);
        gradient.addColorStop(0, `${config.color}40`); // 25% opacity
        gradient.addColorStop(1, `${config.color}00`);
        
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: Array(MAX_CHART_POINTS).fill(''),
                datasets: [{
                    data: Array(MAX_CHART_POINTS).fill(null),
                    borderColor: config.color,
                    backgroundColor: gradient,
                    borderWidth: 1.5,
                    pointRadius: 0,
                    pointHoverRadius: 0,
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                layout: {
                    padding: 0
                },
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false }
                },
                scales: {
                    x: {
                        display: false
                    },
                    y: {
                        display: false,
                        min: config.min,
                        max: config.max
                    }
                }
            }
        });
        
        chartRegistry[`${deviceId}-${sensor}`] = chart;
    });
}

function updateDeviceCharts(deviceId, sensors, isAnomaly, anomalousSensors) {
    const sensorNames = ['temperature', 'vibration', 'current', 'pressure'];
    
    sensorNames.forEach(sensor => {
        const chartId = `${deviceId}-${sensor}`;
        const chart = chartRegistry[chartId];
        if (!chart) return;
        
        const val = sensors[sensor];
        if (val === undefined) return;
        
        const dataset = chart.data.datasets[0];
        
        // Shift data
        dataset.data.push(val);
        if (dataset.data.length > MAX_CHART_POINTS) {
            dataset.data.shift();
        }
        
        // Update color if anomalous
        const baseColor = SENSOR_CONFIG[sensor].color;
        if (isAnomaly && anomalousSensors && anomalousSensors.includes(sensor)) {
            dataset.borderColor = '#ef4444'; // Red for anomaly
            dataset.borderWidth = 2;
        } else {
            dataset.borderColor = baseColor;
            dataset.borderWidth = 1.5;
        }
        
        chart.update('none'); // Update without animation for performance
    });
}

function updateGauge(deviceId, score) {
    const gaugeId = `gauge-${deviceId}`;
    const fillEl = document.querySelector(`#${gaugeId} .gauge-fill`);
    const textEl = document.querySelector(`#${gaugeId} .gauge-text`);
    if (!fillEl || !textEl) return;
    
    // Normalize score (0 to 1) to percentage string
    const percent = Math.min(Math.max(score, 0), 1);
    const scoreVal = (percent * 100).toFixed(0);
    
    textEl.textContent = scoreVal;
    
    // Calculate arc length (path length is approx 251 for r=40, arc 180deg = PI*r = ~125.6)
    // We use viewBox="0 0 120 70", r=40, cx=60, cy=60. Path length for 180deg = ~125.66
    const pathLength = 125.66;
    const offset = pathLength - (percent * pathLength);
    
    fillEl.style.strokeDasharray = `${pathLength}`;
    fillEl.style.strokeDashoffset = offset;
    
    // Color mapping based on score
    let color = 'var(--sev-normal)';
    if (percent > 0.85) color = 'var(--sev-critical)';
    else if (percent > 0.65) color = 'var(--sev-high)';
    else if (percent > 0.4) color = 'var(--sev-medium)';
    else if (percent > 0.2) color = 'var(--sev-low)';
    
    fillEl.style.stroke = color;
}
