# Deploying Hawk-Eye on AWS Lightsail

This is the **plain-English, copy-paste** guide to put the connected Hawk-Eye app
(dashboard + API + AI narratives) on a single AWS Lightsail server. No prior DevOps
knowledge assumed. It takes ~20 minutes.

> **What you get:** a public URL where you log in, ingest an event, watch it become a
> risk-scored alert with a **real AI explanation**, disposition it, and see it audited —
> the full A→Z flow, exactly as demonstrated locally.

---

## 1. What actually gets deployed

One Lightsail instance runs three Docker containers (defined in
[deploy/lightsail/docker-compose.yml](deploy/lightsail/docker-compose.yml)):

```
                 Internet
                    │  :80 (HTTP)  / :443 with TLS
            ┌───────▼────────┐
            │  web (nginx)   │   React dashboard + reverse proxy
            │                │   /  -> the SPA
            │                │   /api, /ws -> backend
            └───┬────────────┘
                │ (private docker network)
        ┌───────▼────────┐        ┌──────────────────────┐
        │ backend        │  ───►  │ gateway              │
        │ FastAPI        │  HTTP  │ ML narrative gateway │
        │ events→alerts  │        │ NEAR AI → Groq → tmpl│
        │ →disposition   │        └──────────────────────┘
        │ →audit         │
        └────────────────┘
```

- **web** — the only container exposed to the internet (port 80).
- **backend** — the control plane (RBAC, alerts, disposition, audit). Internal only.
- **gateway** — turns an alert into a grounded, human-readable narrative. Internal only.
  Tries **NEAR AI** (TEE-attested) first, falls over to **Groq**, then to a deterministic
  template — so the UI never goes dark even if both LLM keys are down or out of credit.

The pilot runs **alert-only and in-process** — no external Kafka/Postgres/ClickHouse
needed to demo the full flow. (You can layer those in later with
[deploy/compose/](deploy/compose/) once you outgrow the pilot.)

---

## 2. Before you start — get two API keys

| Key | Where | Needed? |
|-----|-------|---------|
| `GROQ_API_KEY` | https://console.groq.com/keys | **Yes** — this is the working LLM. Free tier is plenty. |
| `NEAR_AI_API_KEY` | https://cloud.near.ai | Optional — the "primary" TEE provider. If it's out of credit the app **auto-fails over to Groq**, so Groq alone is enough. |

You do **not** need a domain name to start — a raw IP works. (Domain + HTTPS is §7.)

---

## 3. Create the Lightsail instance

**Console path (easiest):**

1. Go to https://lightsail.aws.amazon.com → **Create instance**.
2. Platform **Linux/Unix**, blueprint **OS Only → Ubuntu 24.04 LTS**.
3. Plan: pick at least **4 GB RAM / 2 vCPU** (the `$24/mo`). The first build compiles the
   frontend and installs Python wheels — 1 GB will run out of memory. You can downsize
   later; the running app fits comfortably in 2 GB.
4. Name it `hawkeye-pilot`, **Create instance**.
5. Once it's running, open **Networking → IPv4 Firewall** and add rules:
   - **HTTP** TCP **80** (already there)
   - **HTTPS** TCP **443** (add it, for later)
   - SSH 22 is already open.
6. (Recommended) Attach a **static IP**: Networking → Create static IP → attach to the
   instance. This is the address you'll use.

**CLI path (optional)** — if you have the AWS CLI configured:

```bash
aws lightsail create-instances \
  --instance-names hawkeye-pilot \
  --availability-zone ap-south-1a \
  --blueprint-id ubuntu_24_04 \
  --bundle-id medium_3_0           # 4 GB / 2 vCPU
aws lightsail open-instance-public-ports \
  --instance-name hawkeye-pilot \
  --port-info fromPort=443,toPort=443,protocol=TCP
```

---

## 4. Connect and get the code

SSH in (console: the orange **Connect using SSH** button, or use your key):

```bash
ssh ubuntu@<your-static-ip>
```

Get the repo and move into it:

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/dhruvagrawal27/hawk-eye.git ~/hawk-eye
cd ~/hawk-eye
```

---

## 5. Create your `.env` (the secrets file)

```bash
cp deploy/lightsail/.env.example .env
nano .env          # fill in the blanks, then Ctrl-O, Enter, Ctrl-X to save
chmod 600 .env     # lock it down — only you can read it
```

At minimum set these in `.env`:

```ini
PUBLIC_BASE_URL=http://<your-static-ip>
GROQ_API_KEY=gsk_...                # required (the working LLM)
NEAR_AI_API_KEY=sk-...              # optional (auto-fails over to Groq if empty/out of credit)
PII_HMAC_KEY=<paste 32+ random chars>
HAWKEYE_DEV_JWT_SECRET=<paste 32+ random chars>
```

Generate the two random secrets quickly:

```bash
openssl rand -hex 24    # run twice; paste one into PII_HMAC_KEY, one into HAWKEYE_DEV_JWT_SECRET
```

> The example file is committed (no secrets in it). Your real `.env` is **gitignored** —
> never commit it.

---

## 6. Build and start — one command

```bash
bash deploy/lightsail/bootstrap.sh
```

This installs Docker (if missing), then **builds the three images and starts the stack**.
First run takes ~3–6 minutes (it pulls base images, builds the React app, installs Python
deps). When it finishes it prints your dashboard URL.

Equivalent manual commands if you prefer:

```bash
curl -fsSL https://get.docker.com | sudo sh         # once
sudo docker compose -f deploy/lightsail/docker-compose.yml up -d --build
sudo docker compose -f deploy/lightsail/docker-compose.yml ps
```

You should see all three services `running (healthy)`.

---

## 7. Verify it works (A→Z smoke test)

Open **`http://<your-static-ip>/`** in a browser — the dashboard loads. Log in with the
pilot account `EMP-tl01` / `hawk-eye`.

Or prove the whole pipeline from the shell on the box:

```bash
IP=localhost   # or your static IP from another machine

# 1) log in -> token
TOK=$(curl -s -X POST http://$IP/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"EMP-tl01","password":"hawk-eye"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2) A: ingest one suspicious event -> get an alert
AID=$(curl -s -X POST "http://$IP/api/v1/events/ingest?full=true" \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"event_id":"evt1","ts":"2026-06-30T02:14:07Z","actor":{"employee_id":"EMP-az1","role":"ops_checker","dept":"trade_finance","branch":"BR-219","privileged_flag":true,"tenure_days":2840},"action":{"verb":"approve_payment","channel":"cbs","maker_checker":"checker"},"object":{"beneficiary_id":"BEN-new","account_id":"ACCT-7","amount":4800000,"currency":"INR"},"context":{"is_off_hours":true,"src_ip":"10.20.4.31","device":"WS-114","geo":"Mumbai","session_id":"s1","layer":"application"},"linkage":{"maker_id":"EMP-m9","checker_id":"EMP-az1"}}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['alert']['alert_id'])")
echo "alert: $AID"

# 3) explain it with a REAL AI narrative (provider should be groq or near_ai)
curl -s -X POST "http://$IP/api/v1/narratives/$AID" \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('provider:',d['provider']);print(d['narrative'][:300])"

# 4) Z: disposition -> label written + audited
curl -s -X POST "http://$IP/api/v1/alerts/$AID/disposition" \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"outcome":"fraud","notes":"shell payee"}'
```

Expected: an alert with **risk ~71 (high)**, a **provider: groq** (or `near_ai`) narrative
that mentions off-hours + the ₹48L "just under ₹50L threshold" structuring, and a
disposition response with `label_written: true` and an `audit_id`.

---

## 8. Add a domain + HTTPS (optional but recommended)

1. Point an `A` record for your domain at the static IP.
2. Easiest TLS: put **Caddy** in front (auto Let's Encrypt). On the box:
   ```bash
   sudo apt-get install -y caddy
   echo 'hawkeye.yourdomain.com { reverse_proxy localhost:80 }' | sudo tee /etc/caddy/Caddyfile
   sudo systemctl restart caddy
   ```
   Caddy fetches a certificate automatically. Then set `PUBLIC_BASE_URL=https://hawkeye.yourdomain.com`
   in `.env` and `sudo docker compose -f deploy/lightsail/docker-compose.yml up -d --build web`.
3. Alternatively use a **Lightsail Load Balancer** (it provides a managed certificate) in
   front of the instance on port 80.

---

## 9. Day-2 operations

```bash
C="deploy/lightsail/docker-compose.yml"
sudo docker compose -f $C logs -f            # tail all logs
sudo docker compose -f $C logs -f gateway    # just the LLM gateway
sudo docker compose -f $C ps                 # status/health
sudo docker compose -f $C restart backend    # restart one service
sudo docker compose -f $C down               # stop everything
git pull && sudo docker compose -f $C up -d --build   # deploy an update
```

---

## 10. Production hardening (before real data)

The pilot defaults are demo-grade. Before putting **real** data behind it:

- [ ] Set `PREFLIGHT_MODE=0` and `HAWKEYE_AUTH_MODE=keycloak`; wire a real Keycloak realm
      (the OIDC settings are already in `.env`). The local dev-JWT login is pilot-only.
- [ ] Rotate **every** key/password in `.env` (the example/demo values are not secrets).
- [ ] Terminate TLS (Caddy or Lightsail LB) and redirect 80→443.
- [ ] Restrict SSH (22) to your IP in the Lightsail firewall.
- [ ] Move secrets out of a flat `.env` into a secrets manager (see
      [deploy/secrets/](deploy/secrets/)).
- [ ] Take Lightsail **snapshots** (Storage tab) on a schedule.

---

## 11. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `bootstrap.sh` says *Missing .env* | You skipped §5. `cp deploy/lightsail/.env.example .env` and fill it. |
| Build killed / OOM | Instance too small. Use the 4 GB plan for the build (§3). |
| Dashboard loads but login fails | Backend not healthy yet — `docker compose ... ps`; give it ~30s, check `logs backend`. |
| Narrative says `provider: template` | Both LLM keys are missing/unreachable. Check `GROQ_API_KEY` in `.env` and `logs gateway`. (Template is the safe fallback, not an error.) |
| Narrative says `provider: groq` not `near_ai` | Expected if the NEAR AI key is out of its credit cap — it fails over to Groq by design. |
| `permission denied` on docker | Log out/in once after install (you were added to the `docker` group), or prefix with `sudo`. |

---

**Files used by this deploy**
- [deploy/lightsail/docker-compose.yml](deploy/lightsail/docker-compose.yml) — the 3-service stack
- [deploy/lightsail/Dockerfile.narrative](deploy/lightsail/Dockerfile.narrative) — ML gateway image
- [deploy/lightsail/Dockerfile.frontend](deploy/lightsail/Dockerfile.frontend) — SPA + nginx image
- [deploy/lightsail/nginx.conf](deploy/lightsail/nginx.conf) — reverse proxy
- [deploy/lightsail/bootstrap.sh](deploy/lightsail/bootstrap.sh) — one-shot installer
- [deploy/lightsail/.env.example](deploy/lightsail/.env.example) — config template
- [backend/deploy/Dockerfile.api](backend/deploy/Dockerfile.api) — backend image (reused)
