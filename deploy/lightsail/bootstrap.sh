#!/usr/bin/env bash
# =============================================================================
# Hawk-Eye — Lightsail one-shot bootstrap.
# Run ONCE on a fresh Ubuntu 22.04/24.04 Lightsail instance (as the default user).
# It installs Docker, then builds and starts the pilot stack from this repo.
#
#   curl -fsSL .../bootstrap.sh | bash      # or: bash deploy/lightsail/bootstrap.sh
#
# Prereqs you provide:
#   - this repo checked out at $REPO_DIR
#   - a filled-in .env at $REPO_DIR/.env  (copy from deploy/lightsail/.env.example)
# =============================================================================
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/hawk-eye}"
COMPOSE="deploy/lightsail/docker-compose.yml"

echo "==> Hawk-Eye Lightsail bootstrap"

# --- 1. Docker (engine + compose plugin) ---------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker Engine + compose plugin..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
  echo "    (you may need to log out/in for the docker group to take effect)"
fi

# --- 2. Repo + .env checks ----------------------------------------------
cd "$REPO_DIR"
if [[ ! -f .env ]]; then
  echo "!! Missing $REPO_DIR/.env"
  echo "   cp deploy/lightsail/.env.example .env  &&  edit it  &&  chmod 600 .env"
  exit 1
fi
chmod 600 .env || true

# --- 3. Build + start ----------------------------------------------------
echo "==> Building images (first run pulls base layers; ~3-6 min)..."
sudo docker compose -f "$COMPOSE" build

echo "==> Starting the stack..."
sudo docker compose -f "$COMPOSE" up -d

echo "==> Waiting for health..."
sleep 8
sudo docker compose -f "$COMPOSE" ps

PUB_IP="$(curl -fsS http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo '<your-lightsail-ip>')"
cat <<EOF

============================================================
  Hawk-Eye pilot is up.
  Dashboard : http://${PUB_IP}/
  API health: http://${PUB_IP}/api/v1/  (or /healthz)
  Logs      : sudo docker compose -f ${COMPOSE} logs -f
  Stop      : sudo docker compose -f ${COMPOSE} down
============================================================
EOF
