#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/attendxsuite}"
REPO_URL="${REPO_URL:-https://github.com/Ashutoshazby/AttendXsuite.git}"
SERVICE_USER="${SERVICE_USER:-ubuntu}"
PORT="${PORT:-7860}"
HF_FACE_MODEL="${HF_FACE_MODEL:-buffalo_s}"

if [ -z "${HF_FACE_API_TOKEN:-}" ]; then
  echo "Set HF_FACE_API_TOKEN before running this script."
  echo "Example: export HF_FACE_API_TOKEN='your-long-secret'"
  exit 1
fi

sudo apt-get update
sudo apt-get install -y git python3.11 python3.11-venv python3-pip build-essential cmake libglib2.0-0 libgl1 libsm6 libxext6

if [ ! -d "$APP_DIR/.git" ]; then
  sudo mkdir -p "$APP_DIR"
  sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" pull --ff-only
fi

cd "$APP_DIR/hf-face-api"
python3.11 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt fastapi==0.115.6 "uvicorn[standard]==0.34.0" python-multipart==0.0.20

sudo tee /etc/systemd/system/attendxsuite-face-api.service >/dev/null <<SERVICE
[Unit]
Description=AttendXsuite Face API
After=network.target

[Service]
User=$SERVICE_USER
WorkingDirectory=$APP_DIR/hf-face-api
Environment=HF_FACE_API_TOKEN=$HF_FACE_API_TOKEN
Environment=HF_FACE_MODEL=$HF_FACE_MODEL
ExecStart=$APP_DIR/hf-face-api/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable attendxsuite-face-api
sudo systemctl restart attendxsuite-face-api
sudo ufw allow "$PORT"/tcp || true

echo "AttendXsuite Face API service started on port $PORT."
echo "Check logs: sudo journalctl -u attendxsuite-face-api -f"
