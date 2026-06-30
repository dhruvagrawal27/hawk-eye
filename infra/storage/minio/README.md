# `infra/storage/minio/` — Object store (DATABASE-1)

> **Owner:** DATABASE. MinIO (S3-compatible) is the on-prem equivalent of AWS S3.
> Blueprint **Part 23.3** (encrypted-at-rest, versioned + object-lock,
> least-privilege; l.864-865), **Part 21.5** (partitioned-Parquet datasets;
> l.823-824), **Part 9.3** (immutability/WORM; field-level encryption; l.363-364).

## Buckets (created by `bootstrap_minio.sh`)
| Bucket | Versioning | Object-lock | SSE | Purpose |
|---|---|---|---|---|
| `models` | ON | **ON** (COMPLIANCE, 30d default) | SSE-S3 | Signed model artifacts (DATABASE-7/8) |
| `datasets` | ON | off | SSE-S3 | Partitioned-Parquet datasets + DVC remote (Part 21.5) |
| `feature-snapshots` | ON | off | SSE-S3 | Offline feature snapshots |
| `audit-archive` | ON | **ON** (COMPLIANCE, 3650d default) | SSE-S3 | WORM sealed audit records (DATABASE-6) |
| `clickhouse-cold` | — | — | SSE-S3 | ClickHouse cold tier (DATABASE-3 tiering) |
| `clickhouse-archive` | — | — | SSE-S3 | ClickHouse archive tier (DATABASE-3/9) |

Object-lock **must** be set at bucket creation (`mc mb --with-lock`) — that is why
`models` + `audit-archive` are created separately from the standard buckets.

## Least-privilege RBAC (no principal gets `*` — `policies/*.json`)
| Policy | Service user | Grants | Denies |
|---|---|---|---|
| `models-writer` | `svc-ml-packager` | put/get + set retention on `models/*` | delete, bypass-governance |
| `models-reader` | `svc-serving-loader` | get + list on `models` | put, delete |
| `datasets-rw` | `svc-data-pipeline` | rw on `datasets`,`feature-snapshots` | **any** access to `models`/`audit-archive` |
| `audit-writer` | `svc-worm-writer` | put + **lock** on `audit-archive/*` | delete, bypass-governance, change-lock-config |
| `read-only-auditor` | `svc-auditor` | get + list on all buckets | **all** writes/deletes |

## Encryption at rest (SSE) — and the SSE-KMS swap
Local dev uses **SSE-S3** with a single local KMS key the compose passes via
`MINIO_KMS_SECRET_KEY=hawkeye-key:<base64-32B>` (no external KES needed). Every
object lands encrypted; `mc stat <bucket>/<obj>` shows `Encryption: SSE-S3`.

**1:1 AWS swap (one config change):** point `MINIO_KMS_KES_*` at Vault/KES (or use
AWS KMS) and run `mc encrypt set sse-kms hawkeye-key <bucket>`. The data path,
buckets, policies, and code are unchanged. **PLATFORM owns real key custody**
(Vault/HSM); DATABASE wires the local key for dev (Part 9.3 HSM-for-keys seam).

## Dataset partition layout (Part 21.5)
```
datasets/{dataset_name}/dt=YYYY-MM-DD/source={src}/part-*.parquet   # raw + curated, by date/source
datasets/{dataset_name}/{version}/_content_hash.json               # content hash + feature_set_version
```
DVC remote → `s3://datasets` (this MinIO). Each curated set carries a content hash
(lineage; ties to the model registry `dataset_hash`, DATABASE-8).

## Run
```bash
# via the storage compose (one-shot `minio-setup` runs this automatically):
docker compose -f infra/storage/docker-compose.storage.yml up -d minio minio-setup
# or standalone against a running MinIO:
MINIO_ENDPOINT=http://localhost:9001 ./infra/storage/minio/bootstrap_minio.sh
```
