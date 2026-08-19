import os
import subprocess
import sys

def main():
    print("🚀 Setting up Edge Anomaly Detection Project...")
    
    # 1. Install requirements
    print("📦 Installing requirements...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # 2. Train models
    print("🧠 Training anomaly detection models...")
    subprocess.check_call([sys.executable, "models/train_models.py"])
    
    print("✅ Setup complete! Run the app using: python run.py")

if __name__ == "__main__":
    main()
