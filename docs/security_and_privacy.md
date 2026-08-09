# Security and privacy

## Security objectives

The design seeks confidentiality of telemetry in transit and at rest, integrity
and origin authentication of each parcel, and recoverability after transient
failures. It does not by itself provide vessel enrollment, authorization,
replay prevention, key revocation, transport authentication, or a data
retention policy. Deployments must supply those controls.

## Cryptographic protocol

For each rotated log, the companion plugin signs the raw newline-delimited JSON
using the vessel RSA private key and RSA-SHA256. It prefixes a JSON signature
header, compresses the result with gzip, encrypts it using AES-256-CBC with a
random IV, and wraps a random 32-byte secret using the storage server RSA
public key and PKCS#1 OAEP. The AES key is `SHA-256(secret)`.

The wire format is:

```text
Base64(RSA-OAEP(secret)) + "\n" + AES-CBC(gzip(header + "\n" + log)) + IV
```

The receiver verifies the signature before storing values. It validates PKCS#7
padding and rejects malformed, unsigned, or incorrectly signed payloads. The
legacy leading-IV decoder exists only to recover historical server data; new
clients must use the trailing-IV format.

AES-CBC plus a detached signature provides integrity only when verification is
performed before persistence, as this receiver does. It has no authenticated
encryption tag and has limited algorithm agility. Any protocol redesign should
be versioned and preferably use AEAD (for example AES-GCM or ChaCha20-Poly1305)
with explicit associated data, not silently change the current wire format.

## Key management

| Asset | Location | Required handling |
| --- | --- | --- |
| Server RSA private key | `PRIVATE_KEY_FILENAME` | Keep secret, mode 0600 where supported, back up encrypted, rotate through a planned migration. |
| Server public key | `GET /publickey` | Distribute over authenticated TLS; plugin currently does not pin it. |
| Vessel public keys | `PUBLIC_KEY_ROOT/<context>-public.pem` | Verify fingerprint out of band before installation; restrict write access. |
| Vessel private key | plugin data directory | Never transfer to the server or log it. |

The server automatically creates a 2048-bit RSA key pair when absent. Ensure
the key parent directory already exists and is permission-restricted. A fresh
server private key cannot decrypt previously received parcels, so accidental
regeneration is a data-loss event. Enrollment should record the vessel
identifier, public-key fingerprint, activation time, and revocation status in
an auditable system outside this repository.

## Transport, access control, and network exposure

The application enables CORS and has no application-level authentication on
`/upload` or `/publickey`. Encrypting the parcel does **not** authenticate the
HTTP endpoint, conceal request metadata, prevent storage exhaustion, or stop a
man-in-the-middle replacing the server public key. Terminate HTTPS at a reverse
proxy, authenticate clients (mTLS, a gateway token, or VPN), apply rate/body
size limits, and allow only expected source networks. Keep Redis and PostgreSQL
on private networks and protect their credentials.

The upload route constrains context-derived directory names, but the service
still accepts data before cryptographic verification. Monitor disk quota,
worker failure volume, queue depth, and repeated invalid signatures. Configure
the proxy to reject oversized requests before they consume local storage.

## Privacy and data governance

Signal K deltas can reveal vessel identity, position, routes, speed, nearby
conditions, device state, and crew routines. Encryption protects a parcel but
does not remove obligations under applicable privacy, maritime, contractual,
or research-governance requirements. Define and document:

- purpose and lawful basis for collection;
- datasets and paths collected by each vessel;
- retention period for database rows, `MEDIA_ROOT`, and `TRASH_ROOT`;
- access roles, export controls, and audit records;
- deletion/erasure process, including backups; and
- incident response and vessel-notification procedures.

Restrict database query access to named roles and avoid including full deltas,
keys, or connection strings in logs. Backups require the same access controls
as primary storage. Encrypt persistent volumes where threat modeling calls for
it, and test both restore and secure-deletion procedures.

## Residual risks and hardening roadmap

Prioritize authenticated ingress, key enrollment/revocation, resource limits,
structured audit logging, and an AEAD/versioned parcel protocol. Also maintain
dependency updates, pin container images, run vulnerability scanning, and
perform periodic restore and compromise exercises. Security is a deployment
property shared by the plugin, receiver, reverse proxy, database, Redis, and
operator procedures—not a property of the encryption code alone.
