import aiosqlite
import json
import os
import asyncio

DB_PATH = "data/anomaly_detection.db"

def get_db_connection(db_path: str):
    return aiosqlite.connect(db_path, timeout=30.0)

async def init_db(db_path=DB_PATH):
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    async with get_db_connection(db_path) as db:
        await db.execute('PRAGMA journal_mode=WAL;')
        await db.execute('PRAGMA synchronous=NORMAL;')
        await db.execute('PRAGMA busy_timeout=5000;')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                device_name TEXT,
                timestamp TEXT,
                temperature REAL,
                vibration REAL,
                current REAL,
                pressure REAL,
                anomaly_score REAL,
                is_anomaly BOOLEAN,
                severity TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS anomaly_events (
                id TEXT PRIMARY KEY,
                device_id TEXT,
                device_name TEXT,
                timestamp TEXT,
                severity TEXT,
                message TEXT,
                anomaly_score REAL,
                anomalous_sensors TEXT
            )
        ''')
        
        # Indexes for fast querying
        await db.execute('CREATE INDEX IF NOT EXISTS idx_readings_device_time ON sensor_readings(device_id, timestamp DESC);')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_events_time ON anomaly_events(timestamp DESC);')
        
        await db.commit()

class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.queue = asyncio.Queue()
        self._worker_task = None
        self._running = False
        self.connection = None

    async def start(self):
        self._running = True
        self.connection = await aiosqlite.connect(self.db_path, timeout=30.0)
        await self.connection.execute('PRAGMA journal_mode=WAL;')
        await self.connection.execute('PRAGMA synchronous=NORMAL;')
        await self.connection.execute('PRAGMA busy_timeout=5000;')
        self._worker_task = asyncio.create_task(self._worker_loop())
        print(f"DatabaseManager: Persistent writer started on {self.db_path}")

    async def stop(self):
        self._running = False
        print("DatabaseManager: Draining queue...")
        if self._worker_task:
            await self._drain_queue()
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        if self.connection:
            await self.connection.close()
            self.connection = None
        print("DatabaseManager: Shutdown complete.")

    async def _drain_queue(self):
        while not self.queue.empty():
            try:
                item = self.queue.get_nowait()
                await self._write_item(item)
                self.queue.task_done()
            except asyncio.QueueEmpty:
                break
        if self.connection:
            await self.connection.commit()

    async def _write_item(self, item):
        item_type = item.get("db_type")
        data = item.get("data")
        if item_type == "reading":
            sensors = data.get("sensors", {})
            await self.connection.execute('''
                INSERT INTO sensor_readings 
                (device_id, device_name, timestamp, temperature, vibration, current, pressure, anomaly_score, is_anomaly, severity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get("device_id"), data.get("device_name"), data.get("timestamp"),
                sensors.get("temperature"), sensors.get("vibration"),
                sensors.get("current"), sensors.get("pressure"),
                data.get("anomaly_score", 0.0), data.get("is_anomaly", False),
                data.get("severity", "NORMAL")
            ))
        elif item_type == "alert":
            await self.connection.execute('''
                INSERT INTO anomaly_events 
                (id, device_id, device_name, timestamp, severity, message, anomaly_score, anomalous_sensors)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get("id"), data.get("device_id"), data.get("device_name"),
                data.get("timestamp"), data.get("severity"), data.get("message"),
                data.get("anomaly_score"), json.dumps(data.get("anomalous_sensors", []))
            ))

    async def _worker_loop(self):
        while self._running:
            try:
                # Wait for at least one item, with a timeout so we can check _running
                try:
                    item = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # Process this item and any others that accumulated
                batch_count = 0
                try:
                    await self._write_item(item)
                    self.queue.task_done()
                    batch_count += 1
                    
                    # Drain remaining queued items in this batch
                    while not self.queue.empty() and batch_count < 50:
                        try:
                            item = self.queue.get_nowait()
                            await self._write_item(item)
                            self.queue.task_done()
                            batch_count += 1
                        except asyncio.QueueEmpty:
                            break
                    
                    # Single commit for the whole batch
                    await self.connection.commit()
                except Exception as e:
                    print(f"[DB ERROR] batch write failed: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[DB WORKER ERROR] {e}")
                await asyncio.sleep(0.5)

    def queue_reading(self, reading_data: dict):
        self.queue.put_nowait({"db_type": "reading", "data": reading_data})

    def queue_alert(self, alert_data: dict):
        self.queue.put_nowait({"db_type": "alert", "data": alert_data})

async def insert_reading(db_path: str, reading_data: dict):
    # Fallback legacy function
    async with get_db_connection(db_path) as db:
        sensors = reading_data.get("sensors", {})
        await db.execute('''
            INSERT INTO sensor_readings 
            (device_id, device_name, timestamp, temperature, vibration, current, pressure, anomaly_score, is_anomaly, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            reading_data.get("device_id"),
            reading_data.get("device_name"),
            reading_data.get("timestamp"),
            sensors.get("temperature"),
            sensors.get("vibration"),
            sensors.get("current"),
            sensors.get("pressure"),
            reading_data.get("anomaly_score", 0.0),
            reading_data.get("is_anomaly", False),
            reading_data.get("severity", "NORMAL")
        ))
        await db.commit()

async def insert_alert(db_path: str, alert_data: dict):
    # Fallback legacy function
    async with get_db_connection(db_path) as db:
        await db.execute('''
            INSERT INTO anomaly_events 
            (id, device_id, device_name, timestamp, severity, message, anomaly_score, anomalous_sensors)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            alert_data.get("id"),
            alert_data.get("device_id"),
            alert_data.get("device_name"),
            alert_data.get("timestamp"),
            alert_data.get("severity"),
            alert_data.get("message"),
            alert_data.get("anomaly_score"),
            json.dumps(alert_data.get("anomalous_sensors", []))
        ))
        await db.commit()

async def get_recent_alerts(db_path: str, limit=50) -> list:
    async with get_db_connection(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM anomaly_events ORDER BY timestamp DESC LIMIT ?', (limit,))
        rows = await cursor.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["anomalous_sensors"] = json.loads(d["anomalous_sensors"])
            except Exception:
                d["anomalous_sensors"] = []
            results.append(d)
        return results

async def get_history(db_path: str, device_id=None, limit=100) -> list:
    async with get_db_connection(db_path) as db:
        db.row_factory = aiosqlite.Row
        if device_id:
            cursor = await db.execute('SELECT * FROM sensor_readings WHERE device_id = ? ORDER BY timestamp DESC LIMIT ?', (device_id, limit))
        else:
            cursor = await db.execute('SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT ?', (limit,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def get_stats(db_path: str) -> dict:
    async with get_db_connection(db_path) as db:
        cursor = await db.execute('SELECT COUNT(*) FROM sensor_readings')
        total_readings = (await cursor.fetchone())[0]
        
        cursor = await db.execute('SELECT COUNT(*) FROM anomaly_events')
        total_anomalies = (await cursor.fetchone())[0]
        
        rate = (total_anomalies / total_readings * 100) if total_readings > 0 else 0.0
        
        return {
            "total_readings": total_readings,
            "total_anomalies": total_anomalies,
            "anomaly_rate": round(rate, 2)
        }
