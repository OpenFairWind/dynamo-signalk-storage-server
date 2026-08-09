# DYNAMO Signal K Storage Server

DYNAMO Signal K Storage Server is a shore-side ingestion service for encrypted
Signal K telemetry. It receives signed and encrypted parcels from the
[DYNAMO Signal K Logger plugin](https://github.com/OpenFairWind/dynamo-signalk-logger-plugin),
verifies the vessel signature, decrypts and decompresses the payload in a
Celery worker, and persists the resulting deltas in PostgreSQL/PostGIS.

## What it provides

- HTTP ingestion at `POST /upload/vessels.<selfId>` and server-key discovery at
  `GET /publickey`.
- RSA-OAEP key wrapping, AES-256-CBC parcel encryption, and RSA-SHA256 vessel
  signature verification compatible with the companion plugin.
- Redis-backed asynchronous processing that keeps unsuccessful parcels for
  retry instead of discarding them.
- Dynamic Signal K path tables, including PostGIS point storage for navigation
  positions.
- A Compose deployment with independently restartable web, worker, PostGIS,
  and Redis services plus persistent state volumes.
- A responsive Bootstrap progressive web application shell with an OpenLayers
  map, install metadata, and offline shell caching.

## Documentation

Read these documents before deploying:

- [Architecture](docs/architecture.md) — components, parcel lifecycle, storage
  schema, and delivery/recovery semantics.
- [Getting started](docs/getting_started.md) — local setup, key registration,
  commands, validation, and troubleshooting.
- [Containerization](docs/containerization.md) — the supported Compose
  topology, persistence, networking, and operations.
- [Security and privacy](docs/security_and_privacy.md) — cryptography, key
  management, network exposure, residual risks, and data governance.
- [Agent guidance](AGENTS.md) — repository invariants, tests, and mandatory
  documentation-update rules for contributors and coding agents.

## Quick start with Compose

The default `docker-compose.yml` is a complete local deployment. It exposes
only the receiver on loopback; place a TLS reverse proxy in front of it for
remote access.

```sh
cp .env.sample .env
cp config.json.container.sample config.json
```

Set strong, distinct `POSTGRES_PASSWORD` and `REDIS_PASSWORD` values in
`.env`, then replace the corresponding placeholder values in `config.json`.
The values must match exactly. Register at least one vessel public key after
starting the stack (see the getting-started guide).

```sh
docker compose up --build -d
docker compose ps
docker compose logs -f worker
```

Do not commit `.env`, `config.json`, or generated data under `data/`. They
contain credentials, private key material, or sensitive telemetry.

For host-based Python development, use `docker-compose.yml.development` to run
only PostGIS and Redis, then follow the local workflow in
[getting started](docs/getting_started.md).

## Identity and registration

The application seeds an `admin` account with password `password` for first
startup only. Change or replace it before exposing the service. Administrators
can sign in at `/login`, create groups at `/admin/groups`, and decide whether
public self-registration at `/register` is open. Registration is closed by
default. The authenticated `POST /api/users` endpoint remains administrator
only, allowing controlled provisioning when public registration is closed.

## Verification

After installing the pinned dependencies in an isolated environment, run:

```sh
python -m unittest discover -s tests -v
python -m compileall -q app tests
git diff --check
docker compose config
```

The test suite uses temporary SQLite databases and does not require Redis,
PostgreSQL, or external network services. It covers receiver cryptography,
upload validation and queue hand-off, role/registration policy, SQLAlchemy DAO
behaviour, and PWA assets.

## Research context

The project supports DYNAMO research on secure vessel-to-shore data movement:

- Di Luccio, D., Kosta, S., Castiglione, A., Maratea, A., and Montella, R.
  “Vessel to shore data movement through the internet of floating things: A
  microservice platform at the edge.” *Concurrency and Computation: Practice
  and Experience* 33(4), e5988 (2021). https://doi.org/10.1002/cpe.5988
- Montella, R., Di Luccio, D., Kosta, S., Giunta, G., and Foster, I.
  “Performance, resilience, and security in moving data from the fog to the
  cloud: the DYNAMO transfer framework approach.” ICDCS 2018.
  https://doi.org/10.1007/978-3-030-02738-4_17

## License

Apache License 2.0. See [LICENSE](LICENSE).
