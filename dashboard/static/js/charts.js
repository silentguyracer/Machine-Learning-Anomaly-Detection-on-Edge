// Global chart registry: {"EDGE-001-temperature": Chart instance, ...}
const chartRegistry = {};
let latentScatterChart = null;
let modalTimelineChart = null;

// Sensor config mapping CSS vars to Chart.js
const SENSOR_CONFIG = {
  temperature: { label: 'Temp', color: '#f97316', min: 20, max: 120, unit: '°C' },
  vibration:   { label: 'Vib', color: '#a78bfa', min: 0, max: 1.0, unit: 'g' },
  current:     { label: 'Curr', color: '#22c55e', min: 0, max: 10, unit: 'A' },
  pressure:    { label: 'Press', color: '#38bdf8', min: 0, max: 5, unit: 'bar' },
};

const MAX_CHART_POINTS = 30; // Points for edge mini-charts
const MAX_LATENT_POINTS = 60; // Points for 2D latent scatter

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
        gradient.addColorStop(0, `${config.color}40`);
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
                layout: { padding: 0 },
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false }
                },
                scales: {
                    x: { display: false },
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
        dataset.data.push(val);
        if (dataset.data.length > MAX_CHART_POINTS) {
            dataset.data.shift();
        }
        
        const baseColor = SENSOR_CONFIG[sensor].color;
        if (isAnomaly && anomalousSensors && anomalousSensors.includes(sensor)) {
            dataset.borderColor = '#ef4444';
            dataset.borderWidth = 2;
        } else {
            dataset.borderColor = baseColor;
            dataset.borderWidth = 1.5;
        }
        
        chart.update('none');
    });
}

function updateGauge(deviceId, score) {
    const gaugeId = `gauge-${deviceId}`;
    const fillEl = document.querySelector(`#${gaugeId} .gauge-fill`);
    const textEl = document.querySelector(`#${gaugeId} .gauge-text`);
    if (!fillEl || !textEl) return;
    
    const percent = Math.min(Math.max(score, 0), 1);
    const scoreVal = (percent * 100).toFixed(0);
    
    textEl.textContent = scoreVal;
    const pathLength = 125.66;
    const offset = pathLength - (percent * pathLength);
    
    fillEl.style.strokeDasharray = `${pathLength}`;
    fillEl.style.strokeDashoffset = offset;
    
    let color = 'var(--sev-normal)';
    if (percent > 0.85) color = 'var(--sev-critical)';
    else if (percent > 0.65) color = 'var(--sev-high)';
    else if (percent > 0.4) color = 'var(--sev-medium)';
    else if (percent > 0.2) color = 'var(--sev-low)';
    
    fillEl.style.stroke = color;
}

// 2D Latent Space & PCA Projection Chart
function initLatentChart() {
    const canvas = document.getElementById('latent-scatter-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    latentScatterChart = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [
                {
                    label: 'Normal Operational Envelope',
                    data: [],
                    backgroundColor: 'rgba(59, 130, 246, 0.7)',
                    borderColor: '#3b82f6',
                    pointRadius: 4,
                    pointHoverRadius: 6
                },
                {
                    label: 'Anomaly Outlier Trajectory',
                    data: [],
                    backgroundColor: 'rgba(239, 68, 68, 0.9)',
                    borderColor: '#ef4444',
                    pointRadius: 6,
                    pointHoverRadius: 8
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `Latent [${ctx.parsed.x.toFixed(2)}, ${ctx.parsed.y.toFixed(2)}]`
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#64748b', font: { size: 9 } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#64748b', font: { size: 9 } }
                }
            }
        }
    });
}

function updateLatentChart(coords, isAnomaly) {
    if (!latentScatterChart || !coords || coords.length < 2) return;
    
    const point = { x: coords[0], y: coords[1] };
    const datasetIdx = isAnomaly ? 1 : 0;
    const targetDataset = latentScatterChart.data.datasets[datasetIdx];
    
    targetDataset.data.push(point);
    if (targetDataset.data.length > MAX_LATENT_POINTS) {
        targetDataset.data.shift();
    }
    
    latentScatterChart.update('none');
}

// Modal Timeline Chart
function initModalTimelineChart() {
    const canvas = document.getElementById('modal-timeline-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    modalTimelineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: Array(40).fill(''),
            datasets: [
                { label: 'Temperature (°C)', data: [], borderColor: '#f97316', borderWidth: 2, pointRadius: 0, tension: 0.2 },
                { label: 'Vibration (g)', data: [], borderColor: '#a78bfa', borderWidth: 2, pointRadius: 0, tension: 0.2 },
                { label: 'Current (A)', data: [], borderColor: '#22c55e', borderWidth: 2, pointRadius: 0, tension: 0.2 },
                { label: 'Pressure (bar)', data: [], borderColor: '#38bdf8', borderWidth: 2, pointRadius: 0, tension: 0.2 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: {
                legend: {
                    display: true,
                    labels: { color: '#cbd5e1', boxWidth: 12, font: { size: 11 } }
                }
            },
            scales: {
                x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, display: false },
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } }
            }
        }
    });
}

function updateModalTimelineChart(sensors) {
    if (!modalTimelineChart || !sensors) return;
    
    const keys = ['temperature', 'vibration', 'current', 'pressure'];
    keys.forEach((key, idx) => {
        const ds = modalTimelineChart.data.datasets[idx];
        if (ds && sensors[key] !== undefined) {
            ds.data.push(sensors[key]);
            if (ds.data.length > 40) ds.data.shift();
        }
    });
    
    modalTimelineChart.update('none');
}
