#!/usr/bin/env bash
# Initialise the SoftHSM2 mock-HSM token (PLATFORM-13, blueprint Part 9.3 / 19.3, MOCK).
# SoftHSM is DEV-ONLY — production swaps a physical/cloud HSM (CloudHSM / Luna). This
# gives the platform a real PKCS#11 surface for dev key custody (sign/encrypt) without
# hardware. Requires softhsm2-util + opensc (apt-get install softhsm2 opensc).
set -euo pipefail

export SOFTHSM2_CONF="${SOFTHSM2_CONF:-$(cd "$(dirname "$0")" && pwd)/softhsm2.conf}"
TOKEN_LABEL="${TOKEN_LABEL:-hawk-eye-dev}"
SO_PIN="${SO_PIN:-3537363231}"      # dev PINs only
USER_PIN="${USER_PIN:-1234}"
KEY_LABEL="${KEY_LABEL:-pii-field-key}"

if ! command -v softhsm2-util >/dev/null 2>&1; then
  echo "softhsm2-util not found. Install: apt-get install -y softhsm2 opensc (or brew install softhsm)"
  exit 127
fi

mkdir -p "$(dirname "$SOFTHSM2_CONF")/tokens"
echo "[softhsm] init token '${TOKEN_LABEL}' (SOFTHSM2_CONF=${SOFTHSM2_CONF})"
softhsm2-util --init-token --free --label "$TOKEN_LABEL" --so-pin "$SO_PIN" --pin "$USER_PIN" || \
  echo "[softhsm] token may already exist (continuing)"

# Generate an AES field-encryption key + an RSA signing key inside the token.
MODULE="${PKCS11_MODULE:-/usr/lib/softhsm/libsofthsm2.so}"
if command -v pkcs11-tool >/dev/null 2>&1 && [ -f "$MODULE" ]; then
  pkcs11-tool --module "$MODULE" --login --pin "$USER_PIN" \
    --keygen --key-type aes:32 --label "$KEY_LABEL" --id 01 2>/dev/null || true
  pkcs11-tool --module "$MODULE" --login --pin "$USER_PIN" \
    --keypairgen --key-type rsa:2048 --label "hawk-eye-signing" --id 02 2>/dev/null || true
  echo "[softhsm] keys present:"
  pkcs11-tool --module "$MODULE" --list-objects --login --pin "$USER_PIN" 2>/dev/null | grep -i label || true
fi
echo "[softhsm] DONE — DEV ONLY. Production uses a real HSM (see README.md)."
