#!/usr/bin/env bash
set -euo pipefail

# Local deploy script — wraps gcloud builds submit using cloudbuild.yaml.
#
# Usage:
#   PROJECT_ID=my-project \
#   GCS_BUCKET=mcp-mp-my-project-data \
#   OAUTH_AUDIENCE=https://mcp-mp-xxxxxxxxxx-uc.a.run.app \
#     ./scripts/deploy.sh
#
# Optional overrides:
#   REGION    (default: southamerica-west1)
#   AR_REPO   (default: mcp-mp)
#   SERVICE   (default: mcp-mp)
#
# Requires: gcloud CLI authenticated against the target project.

PROJECT_ID="${PROJECT_ID:?PROJECT_ID env var required}"
REGION="${REGION:-southamerica-west1}"
AR_REPO="${AR_REPO:-mcp-mp}"
SERVICE="${SERVICE:-mcp-mp}"
GCS_BUCKET="${GCS_BUCKET:?GCS_BUCKET env var required}"
OAUTH_AUDIENCE="${OAUTH_AUDIENCE:?OAUTH_AUDIENCE env var required}"

echo "Submitting Cloud Build for project=$PROJECT_ID region=$REGION service=$SERVICE"

gcloud builds submit \
  --project="$PROJECT_ID" \
  --config=cloudbuild.yaml \
  --substitutions="_REGION=$REGION,_AR_REPO=$AR_REPO,_SERVICE=$SERVICE,_GCS_BUCKET=$GCS_BUCKET,_OAUTH_AUDIENCE=$OAUTH_AUDIENCE"

echo ""
echo "Deploy submitted. Watch progress at:"
echo "  https://console.cloud.google.com/cloud-build/builds?project=$PROJECT_ID"
