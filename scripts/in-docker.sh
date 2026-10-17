#!/usr/bin/env bash
# Run a command inside the Aura dev image (glibc / libstdc++ match the Aura build-rel binaries).
#   scripts/in-docker.sh 'python3 -m eac lab ch06/lab1-activation-records'
# Mounts this repo and $AURA_BIN / $AURA_LIB at the same paths. Needs docker (or sudo docker).
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${AURA_IMAGE:-ghcr.io/cybrid-systems/dev:v1.0.9}"
AURA_BIN="${AURA_BIN:-/workspace/aura-eac-bin/aura}"
AURA_LIB="${AURA_LIB:-$(cd "$(dirname "$AURA_BIN")" && pwd)/lib}"
[ -d "$AURA_LIB" ] || AURA_LIB="$(cd "$(dirname "$AURA_BIN")/../lib" && pwd)"
DOCKER="docker"; docker info >/dev/null 2>&1 || DOCKER="sudo docker"
mounts=(-v "$REPO:$REPO")
for p in "$(dirname "$AURA_BIN")" "$AURA_LIB"; do mounts+=(-v "$p:$p"); done
[ -n "${EAC_PROGRESS:-}" ] && mounts+=(-v "$(dirname "$EAC_PROGRESS"):$(dirname "$EAC_PROGRESS")")
# --memory: a runaway rebind (cybrid-systems/aura#4583) must not take the host down
exec $DOCKER run --rm -i --memory="${AURA_EAC_MEM:-4g}" --memory-swap="${AURA_EAC_MEM:-4g}" \
  --entrypoint bash --user "$(id -u):$(id -g)" -e HOME=/tmp "${mounts[@]}" -w "$REPO" \
  -e AURA_BIN="$AURA_BIN" -e AURA_LIB="$AURA_LIB" -e AURA_SANDBOX=off -e AURA_PIPELINE_STRICT=0 \
  -e EAC_PROGRESS="${EAC_PROGRESS:-}" -e PYTHONDONTWRITEBYTECODE=1 \
  "$IMAGE" -c "$*"
