#!/bin/bash
# OpenQueensPark Raspberry Pi Setup Script
set -e

echo "=== OpenQueensPark Raspberry Pi Initializer ==="

# 1. Update system packages
echo "[1/5] Updating system packages..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv sqlite3 git curl

# 2. Setup project virtualenv
echo "[2/5] Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3. Create SQLite Database
echo "[3/5] Initializing SQLite database..."
python3 -c "import database; database.create_tables()"

# 4. Install & Configure Ollama
echo "[4/5] Installing Ollama..."
curl -fsSL https://ollama.com/install.sh | sh

echo "Pulling llama3 model..."
ollama pull llama3

# 5. Install systemd service for OpenQueensPark
echo "[5/5] Configuring systemd auto-start service..."
sudo cp deployment/openqueenspark.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable openqueenspark
sudo systemctl start openqueenspark

echo "=== Setup Complete! OpenQueensPark is running on http://localhost:8501 ==="
