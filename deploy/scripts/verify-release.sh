#!/usr/bin/env bash
# Guard before a prod deploy: the release commit must be on main (so it went through QA) and its
# image must already exist. Prod never rebuilds. Usage: verify-release.sh <sha> <image>
set -euo pipefail

sha="${1:?usage: verify-release.sh <sha> <image>}"
image="${2:?usage: verify-release.sh <sha> <image>}"

if ! git merge-base --is-ancestor "$sha" origin/main; then
  echo "verify-release: ${sha} is not on main" >&2
  exit 1
fi
if ! gcloud artifacts docker images describe "$image" --quiet >/dev/null; then
  echo "verify-release: no image ${image}; it is built on every push to main" >&2
  exit 1
fi
echo "verify-release: ${sha} is on main and ${image} exists"
