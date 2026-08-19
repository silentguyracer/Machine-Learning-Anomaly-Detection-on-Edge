import os
import sys
import subprocess

# Ensure project root is in sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("=========================================")
    print("🚀 EDGE ANOMALY DETECTION SERVER 🚀")
    print("=========================================")
    
    models_dir = os.path.join(project_root, "models", "saved")
    if not os.path.exists(models_dir) or not os.listdir(models_dir):
        print("Models not found. Training models first...")
        subprocess.check_call([sys.executable, os.path.join("models", "train_models.py")])
    
    print("Starting FastAPI server...")
    subprocess.check_call([sys.executable, "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"])

if __name__ == "__main__":
    main()
