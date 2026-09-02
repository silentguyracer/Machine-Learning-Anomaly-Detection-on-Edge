import os
import sys
import subprocess

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("=========================================")
    print("  EDGE ANOMALY DETECTION SERVER")
    print("=========================================")
    
    # Clean stale database locks
    db_dir = os.path.join(project_root, "data")
    for suffix in ["-shm", "-wal"]:
        lock_file = os.path.join(db_dir, f"anomaly_detection.db{suffix}")
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
                print(f"Cleaned stale lock: {lock_file}")
            except OSError:
                pass
    
    models_dir = os.path.join(project_root, "models", "saved")
    if not os.path.exists(models_dir) or not os.listdir(models_dir) or not any(f.endswith('.joblib') for f in os.listdir(models_dir)):
        print("Models not found. Training models first...")
        subprocess.check_call([sys.executable, os.path.join(project_root, "models", "train_models.py")], cwd=project_root)
    
    print("Starting FastAPI server on http://localhost:8000 ...")
    print("Open your browser to http://localhost:8000")
    print()
    subprocess.check_call(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=project_root
    )

if __name__ == "__main__":
    main()
