# NAS Deployment Blueprint

This is a deployment design, not a runnable Compose file or production installation.

## Topology

```text
LAN/TLS
   |
reverse-proxy  ->  web  ->  database
                      \-> optional worker
backup-job ----------------> database/releases/backups
```

Required services are `web`, `database`, `reverse-proxy`, and `backup-job`; `worker` is optional for imports, exports, validation, and release assembly. Only the reverse proxy publishes a host port. PostgreSQL remains on an internal network.

## Service Contract

| Service | Responsibility | Health check | Depends on |
|---|---|---|---|
| `database` | PostgreSQL data and transactions | `pg_isready` plus schema compatibility query | durable database volume |
| `web` | Web UI and `/api/v1` | `/health/live` and `/health/ready` | healthy database, readable release/source mounts |
| `reverse-proxy` | TLS, request limits, security headers, routing | local HTTPS probe | healthy Web |
| `backup-job` | physical/logical backups, hashes, retention, restore drills | latest successful verified backup age | healthy database, writable backups |
| `worker` | queued non-interactive jobs | heartbeat and queue lag | database, releases, read-only source |

Compose startup conditions are convenience only. Each service must retry dependencies safely and fail readiness until compatible.

## NAS Directories and Mounts

`PLATFORM_ROOT` contains:

- `source`: `/srv/platform/source`, mounted read-only in Web and worker.
- `database`: `/var/lib/postgresql/data`, writable only by PostgreSQL.
- `releases`: `/srv/platform/releases`, read-only in Web; writable only by controlled release/backup jobs.
- `exports`: `/srv/platform/exports`, writable for generated user exports; non-authoritative.
- `backups`: `/srv/platform/backups`, writable only by backup tooling and read during restore.
- `logs`: `/srv/platform/logs`, append-oriented with rotation and secret redaction.

The private `deployment_volume_matrix.csv` defines access, retention, and restore order. Source authority files are never written by a container.

## Environment Variables

Minimum configuration:

- `PLATFORM_ENV`, `PLATFORM_ROOT`, `APP_VERSION`, `API_BASE_PATH`
- `DATABASE_URL` via secret, `POSTGRES_DB`, `POSTGRES_USER`, password secret file
- `REFERENCE_RELEASE_ID`, `MAPPING_RELEASE_ID`, optional enterprise release IDs
- `RELEASE_MANIFEST_PATH`, `EXPECTED_SCHEMA_VERSION`
- `PUBLIC_BASE_URL`, `TRUSTED_PROXY_CIDRS`, `SESSION_SECRET_FILE`
- `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET_FILE` when OIDC is enabled
- `BACKUP_SCHEDULE`, `BACKUP_RETENTION_DAYS`, `BACKUP_ENCRYPTION_KEY_FILE`
- `LOG_LEVEL`, `LOG_FORMAT=json`, `TZ=Asia/Shanghai`

Secrets are Docker secrets or NAS secret files with least privilege; they are never embedded in images, Compose, manifests, logs, or exports.

## Images, Logging, and Networks

- Pin images by immutable digest and record the human-readable tag in the Release Manifest.
- Use separate `edge` and `backend` networks. Database and worker have no public ports.
- Emit structured logs with timestamp, service, version, correlation ID, actor ID, and event code; omit source content and secrets by default.
- Configure size/time rotation and NAS disk alerts. Security and domain audit records live in PostgreSQL as governed events, not only log files.

## Backup

1. Nightly physical PostgreSQL backup with WAL strategy appropriate to NAS capacity.
2. Daily logical dump for portability.
3. Copy active and prior Release Manifests, migration hashes, configuration inventory, and source hash inventory.
4. Hash and encrypt every backup bundle, then copy it off the NAS.
5. Monitor backup age and perform scheduled restore drills to an isolated database.

## Restore

1. Isolate traffic and preserve the failed state for investigation.
2. Verify backup checksum, encryption material, application image digest, schema version, and manifests.
3. Restore PostgreSQL to a clean volume; never restore over the only copy.
4. Restore release manifests and validate source hashes against read-only Source.
5. Start database, run compatibility checks, then Web/worker, then reverse proxy.
6. Run smoke checks and reconcile active release pointers before reopening traffic.

## Upgrade and Rollback

Upgrade order: verified backup -> pull pinned images -> migration preflight -> additive/backward-compatible schema migration -> data release import/validation -> Web/worker -> smoke -> reverse proxy activation. Destructive schema cleanup is deferred to a later release.

Rollback first repoints the composite Release Manifest and application image to the last compatible version. Database migrations prefer roll-forward repair; physical restore is the last resort. Rollback never edits immutable Reference, Mapping, price, or quota release rows.

