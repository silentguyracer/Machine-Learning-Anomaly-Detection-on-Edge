# 🔬 Machine Learning Anomaly Detection on Edge

A production-grade **Edge AI Anomaly Detection System** for industrial IoT monitoring. Runs multiple ML models locally on the edge for real-time anomaly detection with a stunning live dashboard.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  EDGE SIMULATOR LAYER                                       │
│  5 Virtual Devices: Alpha Motor, Beta Compressor, ...       │
│  Sensors: Temperature, Vibration, Current, Pressure         │
│  Anomaly Injection: Spike, Drift, Oscillation, Flatline     │
└─────────────────────┬───────────────────────────────────────┘
                      │ sensor readings every 0.5s
┌─────────────────────▼───────────────────────────────────────┐
│  ML INFERENCE ENGINE                                        │
│  • Isolation Forest (sklearn)   — global outlier detection  │
│  • Local Outlier Factor (LOF)   — density-based detection   │
│  • Statistical Z-Score          — per-sensor baseline       │
│  • Range Rules                  — hard operational limits   │
│  Ensemble: weighted voting → anomaly_score [0-1]            │
└─────────────────────┬───────────────────────────────────────┘
                      │ WebSocket streaming
┌─────────────────────▼───────────────────────────────────────┐
│  FASTAPI BACKEND                                            │
│  • WebSocket /ws — real-time push to dashboard              │
│  • REST API — history, stats, alerts                        │
│  • SQLite — anomaly event persistence                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│  WEB DASHBOARD (localhost:8000)                             │
│  • Real-time sensor charts (Chart.js)                       │
│  • Anomaly score gauge per device                           │
│  • Live alert feed with severity levels                     │
│  • System metrics bar                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Install Dependencies & Train Models
```bash
python setup.py
```

### 2. Run the System
```bash
python run.py
```

### 3. Open the Dashboard
Navigate to **http://localhost:8000** in your browser.

---

## 📦 Dependencies

```
fastapi, uvicorn, scikit-learn, numpy, pandas, aiosqlite, jinja2, scipy, joblib, websockets
```

Install with: `pip install -r requirements.txt`

---

## 🔬 ML Models

| Model | Algorithm | Type | Purpose |
|-------|-----------|------|---------|
| Isolation Forest | sklearn | Tree-based | Global outlier detection |
| Local Outlier Factor | sklearn | Distance-based | Density anomalies |
| Statistical Z-Score | NumPy/SciPy | Statistical | Per-sensor baseline |
| Range Rules | Rule-based | Hard limits | Operational safety bounds |

**Ensemble Weight:** IF(35%) + LOF(15%) + Statistical(30%) + Range(20%)

---

## 📡 Simulated Devices

| ID | Name | Specialty |
|----|------|-----------|
| EDGE-001 | Alpha Motor | General motor monitoring |
| EDGE-002 | Beta Compressor | High-vibration system |
| EDGE-003 | Gamma Turbine | High-temperature system |
| EDGE-004 | Delta Pump | High-current system |
| EDGE-005 | Epsilon Generator | Pressure-sensitive system |

**Anomaly Types:** Spike (sudden outlier), Drift (gradual shift), Oscillation (rapid swings), Flatline (sensor fault)

**Anomaly Rate:** ~12% for demo visibility

---

## 📊 Sensor Parameters

| Sensor | Unit | Normal Range | Anomaly Impact |
|--------|------|-------------|----------------|
| Temperature | °C | 50–90 | Overheating, thermal runaway |
| Vibration | g | 0–0.5 | Bearing wear, imbalance |
| Current | A | 3–7 | Overload, short circuit |
| Pressure | bar | 1–3.5 | Leaks, blockages |

---

## 🌐 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard UI |
| `/ws` | WebSocket | Real-time data stream |
| `/api/stats` | GET | System statistics |
| `/api/alerts` | GET | Recent anomaly alerts |
| `/api/history` | GET | Sensor reading history |
| `/api/devices` | GET | Device list |

---

## 🏗️ Project Structure

```
├── requirements.txt
├── setup.py               # Auto-setup: install deps + train models
├── run.py                 # Single-command launcher
│
├── models/
│   ├── train_models.py    # Model training script
│   └── saved/             # Trained model files (.pkl)
│
├── core/
│   ├── anomaly_detector.py    # Ensemble ML detection engine
│   ├── feature_extractor.py   # Sliding window + Z-score
│   └── alert_manager.py       # Alert severity + messages
│
├── edge_simulator/
│   ├── sensor_simulator.py    # Realistic sensor data generation
│   └── device_manager.py      # Multi-device async orchestrator
│
├── api/
│   ├── main.py               # FastAPI app
│   ├── database.py           # SQLite async operations
│   └── routes/
│       ├── websocket.py      # WebSocket endpoint
│       └── data.py           # REST API routes
│
├── dashboard/
│   ├── templates/index.html  # Dashboard UI
│   └── static/
│       ├── css/style.css     # Dark glassmorphism theme
│       └── js/               # Chart.js, alerts, WebSocket logic
│
└── data/
    └── anomaly_detection.db  # SQLite database (auto-created)
```

---

## ⚙️ Configuration

Edit device configs in `edge_simulator/sensor_simulator.py`:
- `anomaly_rate`: Fraction of readings that are anomalous (default: 0.12)
- `DEVICE_CONFIGS`: Device names and base sensor values

Edit detection thresholds in `core/anomaly_detector.py`:
- `SENSOR_RANGES`: Normal operating ranges per sensor
- Ensemble weights in `detect()` method

---

## 📈 Dashboard Features

- **Real-time charts**: 60-point sliding window per sensor per device
- **Anomaly gauge**: SVG arc gauge (0–100%) with color shift
- **Alert feed**: Live anomaly alerts with severity, device, affected sensors
- **System stats**: Total readings, anomaly rate, active devices, uptime
- **Model verdicts**: Per-model indicator badges (IF, LOF, STAT)
- **Auto-reconnect**: WebSocket reconnects automatically if connection drops

---

## 🔧 Manual Model Training

```bash
python models/train_models.py
```

This trains models on 5,000 samples of synthetic normal operating data and saves them to `models/saved/`.

---

*Built with FastAPI, scikit-learn, Chart.js, and WebSockets.*
