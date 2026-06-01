#!/usr/bin/env bash
set -euo pipefail

# Local deploy script — wraps gcloud builds submit using cloudbuild.yaml.
#
# Usage:
#   PROJECT_ID=my-project \
#   GCS_BUCKET=mcp-mp-my-project-data \
#   OAUTH_AUDIENCE=https://mcp-mp-xxxxxxxxxx.run.app \
#   ALLOWED_HOSTS=mcp-mp-xxxxxxxxxx.run.app \
#     ./scripts/deploy.sh
#
# Optional overrides:
#   REGION         (default: southamerica-west1)
#   AR_REPO        (default: mcp-mp)
#   SERVICE        (default: mcp-mp)
#   AUTH_PROVIDER  (default: header  — switch to "google" once OAuth is configured)
#   SHORT_SHA      (default: derived from git HEAD; falls back to "manual")
#
# Requires: gcloud CLI authenticated against the target project.

PROJECT_ID="${PROJECT_ID:?PROJECT_ID env var required}"
REGION="${REGION:-southamerica-west1}"
AR_REPO="${AR_REPO:-mcp-mp}"
SERVICE="${SERVICE:-mcp-mp}"
GCS_BUCKET="${GCS_BUCKET:?GCS_BUCKET env var required}"
OAUTH_AUDIENCE="${OAUTH_AUDIENCE:?OAUTH_AUDIENCE env var required}"
ALLOWED_HOSTS="${ALLOWED_HOSTS:-}"
AUTH_PROVIDER="${AUTH_PROVIDER:-header}"

# SHORT_SHA is set automatically by Cloud Build for git-triggered builds, but
# not for manual `gcloud builds submit`. Derive it from the local checkout so
# the image gets a meaningful tag instead of the random BUILD_ID.
SHORT_SHA="${SHORT_SHA:-$(git rev-parse --short=7 HEAD 2>/dev/null || echo manual)}"

echo "Submitting Cloud Build:"
echo "  project = $PROJECT_ID"
echo "  region  = $REGION"
echo "  service = $SERVICE"
echo "  sha     = $SHORT_SHA"
echo "  auth    = $AUTH_PROVIDER"

gcloud builds submit \
  --project="$PROJECT_ID" \
  --config=cloudbuild.yaml \
  --substitutions="SHORT_SHA=$SHORT_SHA,_REGION=$REGION,_AR_REPO=$AR_REPO,_SERVICE=$SERVICE,_GCS_BUCKET=$GCS_BUCKET,_GCP_PROJECT=$PROJECT_ID,_OAUTH_AUDIENCE=$OAUTH_AUDIENCE,_ALLOWED_HOSTS=$ALLOWED_HOSTS,_AUTH_PROVIDER=$AUTH_PROVIDER"

echo ""
echo "Deploy submitted. Watch progress at:"
echo "  https://console.cloud.google.com/cloud-build/builds?project=$PROJECT_ID"
