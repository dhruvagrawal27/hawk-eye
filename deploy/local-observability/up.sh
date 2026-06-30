#!/usr/bin/env bash
# =============================================================================
# Hawk-Eye — bring up native Grafana + Prometheus (macOS, brew) and KEEP them up.
# Uses `brew services` (launchd) so both survive logout/reboot and auto-restart.
# Prometheus scrapes the running backend's /metrics; Grafana serves the
# hawk-eye-ops dashboard the dashboard embed points at (anonymous + embeddable).
#
#   bash deploy/local-observability/up.sh
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="$(brew --prefix)"
PROV="$HERE/grafana/provisioning"

command -v grafana >/dev/null 2>&1 || { echo "!! grafana not installed — run: brew install grafana"; exit 1; }
command -v prometheus >/dev/null 2>&1 || { echo "!! prometheus not installed — run: brew install prometheus"; exit 1; }

echo "==> Prometheus: install scrape config -> $PREFIX/etc/prometheus.yml"
cp "$HERE/prometheus.yml" "$PREFIX/etc/prometheus.yml"

echo "==> Grafana: patch grafana.ini (anonymous + embedding + provisioning)"
GINI="$PREFIX/etc/grafana/grafana.ini"
[ -f "$GINI" ] || { echo "!! $GINI not found"; exit 1; }
cp "$GINI" "$GINI.hawkeye.bak" 2>/dev/null || true
python3 "$HERE/patch_grafana_ini.py" "$GINI" "$PROV"

echo "==> Starting services under launchd (brew services)"
brew services restart prometheus
brew services restart grafana

echo "==> Waiting for Grafana :3000 ..."
for i in $(seq 1 30); do
  if /usr/bin/curl -fsS -m2 http://localhost:3000/api/health >/dev/null 2>&1; then break; fi
  sleep 1
done

echo ""
echo "── status ──"
/usr/bin/curl -s -m3 http://localhost:9090/-/healthy && echo " (prometheus :9090)" || echo "prometheus not ready"
/usr/bin/curl -s -m3 http://localhost:3000/api/health | head -c 200; echo " (grafana :3000)"
echo ""
echo "Dashboard embed URL: http://localhost:3000/d/hawk-eye-ops?kiosk"
echo "Both run under launchd — they restart on boot. Stop with:"
echo "  brew services stop grafana && brew services stop prometheus"
