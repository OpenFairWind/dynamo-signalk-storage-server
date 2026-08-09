#!/bin/sh
set -eu

# State is normally a mounted volume. Create the complete hierarchy on first
# start without ever creating or copying a configuration or a private key.
mkdir -p data/keys/public data/media data/scratch data/trash

exec "$@"
