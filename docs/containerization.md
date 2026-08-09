# Containerization

## Deployment topology

Containerize the receiver as three independently restartable processes:

| Service | Role | Persistent volume required |
| --- | --- | --- |
| PostgreSQL/PostGIS | telemetry database | database data directory |
| Redis | Celery broker/result backend | recommended for recovery and observability |
| web and worker | separate instances of the same application image | configuration, keys, media, scratch, and trash |

Do not run the web process and worker in a single container. Independent
lifecycles let uploads remain available during worker restarts and allow worker
replicas to be scaled. Every worker replica must mount the same parcel/key
storage or use an equivalent shared durable volume.

## Current repository artifacts

`docker-compose.yml` is the complete Compose baseline. It builds the
application image, starts isolated PostGIS and Redis services, and runs the
Flask receiver and Celery worker separately. It mounts `config.json` read-only
and stores keys, queued parcels, scratch data, and archived parcels in the
shared `dynamo-state` named volume. `docker-compose.yml.development` starts
only PostGIS and Redis for host-based Python development.

Before starting the complete stack, copy `.env.sample` to `.env` and
`config.json.container.sample` to `config.json`, then replace every password
placeholder in both files with the same strong values. Both files are ignored
operational state and must not be committed.

## Build an application image

The repository `Dockerfile` is the application image definition. Build and
validate the deployment with:

```sh
docker compose config
docker compose up --build -d
docker compose ps
```

Pin base-image digests in a production build, generate an SBOM, and scan the
final image. The pinned Python dependencies should be reviewed regularly;
containerization does not compensate for vulnerable application dependencies.

## Compose design

PostGIS and Redis are on an internal-only `backend` network and have no host
ports. The receiver is bound to `127.0.0.1:${DYNAMO_PORT}`; expose it externally
only through a TLS-terminating, authenticated reverse proxy. Health checks
gate web/worker startup on database and broker availability. Because startup
scans `MEDIA_ROOT`, do not replace `dynamo-state` with an ephemeral filesystem.

For production, replace the local image tag with an immutable registry digest,
provide configuration and secrets through the platform’s secret mechanism, and
pre-provision persistent volumes with restrictive ownership. The supplied
Compose stack is a reproducible baseline, not a substitute for platform-level
backup, monitoring, ingress authentication, or secret rotation.

## Operations and upgrades

Back up PostgreSQL and the server private key as a matched recovery set. Before
rolling an upgrade, drain or preserve `MEDIA_ROOT`; once a parcel has been
processed it is retained in `TRASH_ROOT`, subject to the organization’s
retention policy. Test restores in an isolated environment using the original
key and registered vessel public keys. Scale workers cautiously because the
same parcel should not be submitted concurrently by multiple workers.
