#!/usr/bin/env bash
# Unit + lab tests. Needs the Aura binary; use --docker to run inside the dev image.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [ "${1:-}" = "--docker" ]; then exec scripts/in-docker.sh "python3 -m unittest discover -s tests -v"; fi
exec python3 -m unittest discover -s tests -v
