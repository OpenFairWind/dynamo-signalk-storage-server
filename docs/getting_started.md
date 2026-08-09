# Getting started

## Prerequisites

Use a Unix-like environment with Python 3.8+ (the supplied Docker image starts
from Python 3.8), PostgreSQL with PostGIS, Redis, and OpenSSL. The companion
logger plugin must be configured with the URL of this receiver. Run all
commands below from the repository root; configuration paths are interpreted
relative to that working directory.

## 1. Create an isolated Python environment

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`psycopg2-binary==2.9.6` predates some newer Python releases. If pip attempts a
source build, use a supported Python version or install PostgreSQL development
tools that provide `pg_config`.

## 2. Start dependencies

For host-based development, use the dependency-only Compose configuration:

```sh
docker compose -f docker-compose.yml.development up -d postgis redis
```

The sample database is exposed on `127.0.0.1:5432`, with database/user
`dynamo` and password `Dynamo2022`; change these values before any shared or
production deployment. Redis is exposed on `127.0.0.1:6379` without a
password, which is acceptable only for isolated development.

Confirm readiness before continuing:

```sh
docker compose -f docker-compose.yml.development ps
docker compose -f docker-compose.yml.development exec postgis pg_isready -U dynamo -d dynamo
docker compose -f docker-compose.yml.development exec redis redis-cli ping
```

## 3. Configure state and credentials

```sh
cp config.json.sample config.json
mkdir -p data/keys/public data/media data/scratch data/trash
chmod 700 data/keys data/keys/public
chmod 600 config.json
```

Edit `config.json` and set `CONNECTION_STRING`, `MEDIA_ROOT`, `SCRATCH_ROOT`,
`TRASH_ROOT`, and the Celery endpoints for your environment. At first startup
the application creates the server RSA key pair if absent. Back up the private
key securely; losing it makes existing parcels undecryptable. Do not commit
`config.json` or any files below `data/keys`.

## 4. Register a vessel key

The server cannot authenticate a vessel until its public RSA key has been
installed under the exact name expected by the upload context. Obtain the
public key from the plugin’s authenticated `/publickey` endpoint, verify its
fingerprint through an independent channel, then install it:

```sh
install -m 0644 /path/to/vessel-public.pem \
  data/keys/public/vessels.urn:mrn:signalk:uuid:EXAMPLE-public.pem
```

The `EXAMPLE` string must exactly match the plugin `selfId`; it is appended to
`vessels.` in the upload URL. The plugin separately obtains the storage
server’s public key from `GET /publickey`.

## 5. Run the worker and receiver

Use separate terminals with the virtual environment activated in both:

```sh
celery --app run.celery_app worker --loglevel=INFO
```

```sh
flask --app run:flask_app run --host 0.0.0.0 --port 13387
```

The receiver listens at `http://127.0.0.1:13387` by default. In production,
bind privately and expose it through a TLS-terminating reverse proxy.

## 6. Verify an end-to-end transfer

1. Fetch `GET /publickey` and configure that key in the logger plugin.
2. Configure the plugin’s server URL and trigger a log rotation/upload.
3. Observe the HTTP response and Celery worker log.
4. Verify that the parcel moved from `data/media/<context>/` to
   `data/trash/<context>/` only after successful processing.
5. Query PostgreSQL, for example:

```sh
docker compose -f docker-compose.yml.development exec postgis psql -U dynamo -d dynamo \
  -c 'SELECT context, timestamp, value FROM navigation_speedOverGround LIMIT 10;'
```

Run the receiver regression tests after installing dependencies:

```sh
python -m unittest discover -s tests -v
```

## Troubleshooting

| Symptom | Likely cause and action |
| --- | --- |
| Upload is accepted but never stored | Ensure a Celery worker is running and pointed to the same Redis broker. |
| `Public key file missing` | Register the vessel public key using the precise context-derived filename. |
| Parcel remains in `media` | Read the worker exception; the parcel is intentionally retained for retry. |
| Database connection error | Check PostGIS readiness and the connection string. |
| Invalid signature | Re-register the correct vessel public key; do not alter parcel bytes. |
