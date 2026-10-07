#!/usr/bin/env bash
# Deploy one image to one environment (QA or prod). Usage: deploy-env.sh <image>
# Env: GCP_REGION, SERVICE_NAME, MIGRATE_JOB_NAME.
#   1. point the migration job at the image and run it; stop if it fails;
#   2. deploy a new revision with no traffic, tagged "candidate";
#   3. smoke check the candidate URL; stop if it fails (traffic stays on the previous revision);
#   4. move 100% of traffic to the new revision.
# Migrations must stay backwards compatible (expand/contract): the previous revision keeps
# serving on the migrated schema until step 4.
set -euo pipefail

image="${1:?usage: deploy-env.sh <image>}"
region="${GCP_REGION:?}"
service="${SERVICE_NAME:?}"
job="${MIGRATE_JOB_NAME:?}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "::group::migrate (${job})"
gcloud run jobs update "$job" --region "$region" --image "$image" --quiet
gcloud run jobs execute "$job" --region "$region" --wait --quiet
echo "::endgroup::"

echo "::group::deploy candidate (${service})"
gcloud run deploy "$service" --region "$region" --image "$image" --no-traffic --tag candidate --quiet
candidate_url=$(gcloud run services describe "$service" --region "$region" --format=json \
  | jq -r '.status.traffic[] | select(.tag == "candidate") | .url // empty')
echo "::endgroup::"

if [ -z "$candidate_url" ]; then
  echo "deploy-env: no URL for the candidate tag on ${service}; traffic left on the previous revision" >&2
  exit 1
fi

"$script_dir/smoke.sh" "$candidate_url"

gcloud run services update-traffic "$service" --region "$region" --to-latest --quiet
url=$(gcloud run services describe "$service" --region "$region" --format='value(status.url)')
echo "deployed ${image} to ${url}"
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "url=${url}" >>"$GITHUB_OUTPUT"
fi
