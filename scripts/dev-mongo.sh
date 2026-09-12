#!/usr/bin/env bash
# Download and run a project-local MongoDB for tests. No Docker, no sudo.
set -euo pipefail

MONGO_VERSION="8.0.15"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/.tools"
MONGO_DIR="$TOOLS/mongodb-linux-x86_64-ubuntu2404-$MONGO_VERSION"
MONGOD="$MONGO_DIR/bin/mongod"

if [ ! -x "$MONGOD" ]; then
  echo "Downloading MongoDB $MONGO_VERSION..." >&2
  mkdir -p "$TOOLS"
  curl -fsSL "https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2404-$MONGO_VERSION.tgz" \
    | tar -xz -C "$TOOLS"
fi

echo "$MONGOD"
