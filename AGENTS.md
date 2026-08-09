# Repository guidance for coding agents

## Scope and invariants

- Preserve compatibility with the DYNAMO Signal K logger parcel protocol. Do
  not change the on-wire layout, cryptographic algorithms, key naming, or
  acknowledgement semantics without coordinated changes to the companion
  plugin, regression tests, and documentation.
- A parcel is archival evidence. Never delete or move it to `TRASH_ROOT` until
  decryption, signature verification, and database persistence have succeeded.
- Treat `config.json`, private keys, registered vessel keys, media parcels,
  telemetry, database credentials, and Redis credentials as sensitive. Do not
  commit, print, fixture, or log their real contents.
- Keep paths safe: data derived from HTTP input must not be able to escape its
  configured directory. Preserve the accepted Signal K context identifier
  format when changing upload handling.

## Development and verification

- Target the Python versions supported by the Docker image and pinned
  dependencies. Keep `requirements.txt` pinned; explain and test dependency
  changes.
- For web-interface changes, preserve responsive Bootstrap layouts, PWA
  manifest/service-worker behaviour, accessible controls, and the OpenLayers
  integration. Update README and operational documentation whenever the web
  surface or browser requirements change.
- Add or update focused tests for every behavioural fix, especially parcel
  decoding, signature verification, upload handling, database persistence, and
  failure/retry paths.
- Run `python -m unittest discover -s tests -v`, `python -m compileall -q app
  tests`, and `git diff --check` before handing off a Python change. The suite
  must cover parcel decoding, HTTP validation, authorization, DAO behaviour,
  and the PWA shell. Run
  `docker compose config` after Compose changes when Docker is available.
- Preserve user-owned untracked configuration, generated keys, media, local
  Compose overrides, and IDE files unless the user explicitly asks to change
  them.

## Documentation is part of the change

Documentation must be updated in the same change whenever a code, dependency,
configuration, deployment, protocol, operational, or security change affects
users or operators. Apply the following routing:

| Change type | Documentation that must be reviewed and updated when affected |
| --- | --- |
| Parcel format, encryption, signatures, or keys | `docs/architecture.md`, `docs/security_and_privacy.md`, companion plugin protocol documentation, and tests |
| Routes, queueing, persistence, recovery, or schema | `docs/architecture.md`, `docs/getting_started.md`, and README |
| Local setup, dependencies, environment variables, or commands | `README.md` and `docs/getting_started.md` |
| Docker image, Compose, volumes, networks, or production operations | `docs/containerization.md`, `docs/getting_started.md`, and README |
| Privacy, authorization, retention, logging, or exposure | `docs/security_and_privacy.md` and README when the user-facing posture changes |

Do not claim a command or deployment is reproducible unless it has been
validated or any prerequisite/limitation is stated explicitly. Keep Markdown
links valid and keep the README concise: it is the entry point; the `docs/`
files hold the deeper narrative.

## Git and release hygiene

- Use focused commits. Stage only requested source, test, deployment, and
  documentation files; never stage local configuration or generated data.
- Do not publish packages, images, releases, tags, or credentials without
  explicit user authorization.
- When changing a security-sensitive component, state the threat-model impact
  and any residual limitation in the final handoff.
