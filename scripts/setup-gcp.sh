#!/usr/bin/env bash
set -euo pipefail

# Bootstrap script for the GCP project. Idempotent — safe to re-run.
#
# Usage:
#   PROJECT_ID=my-project ./scripts/setup-gcp.sh
#
# Optional overrides:
#   REGION      (default: southamerica-west1)
#   AR_REPO     (default: mcp-mp)
#   SERVICE     (default: mcp-mp)
#   GCS_BUCKET  (default: mcp-mp-${PROJECT_ID}-data)
#
# What it does:
#   1. Enables required GCP APIs.
#   2. Creates the Artifact Registry Docker repository.
#   3. Creates the GCS bucket for tenant storage (uniform bucket-level access).
#   4. Creates the runtime service account with minimum required IAM roles.
#   5. Grants the Cloud Build SA permission to deploy Cloud Run services.

PROJECT_ID="${PROJECT_ID:?PROJECT_ID env var required}"
REGION="${REGION:-southamerica-west1}"
AR_REPO="${AR_REPO:-mcp-mp}"
SERVICE="${SERVICE:-mcp-mp}"
GCS_BUCKET="${GCS_BUCKET:-mcp-mp-${PROJECT_ID}-data}"
RUNTIME_SA="mcp-mp-runtime"

echo "Project : $PROJECT_ID"
echo "Region  : $REGION"
echo "Bucket  : $GCS_BUCKET"
echo "AR repo : $AR_REPO"
echo ""

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
CB_SA="$PROJECT_NUMBER@cloudbuild.gserviceaccount.com"

echo "Step 1/5 — Enabling APIs..."
gcloud services enable \
  --project="$PROJECT_ID" \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  iam.googleapis.com

echo "Step 2/5 — Creating Artifact Registry repo (if not exists)..."
gcloud artifacts repositories create "$AR_REPO" \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --repository-format=docker \
  --description="MCP Mercado Publico container images" \
  2>/dev/null || echo "  (already exists, skipping)"

echo "Step 3/5 — Creating GCS bucket (if not exists)..."
gsutil mb -p "$PROJECT_ID" -l "$REGION" -b on "gs://$GCS_BUCKET" 2>/dev/null || echo "  (already exists, skipping)"

echo "Step 4/5 — Creating runtime service account (if not exists)..."
gcloud iam service-accounts create "$RUNTIME_SA" \
  --project="$PROJECT_ID" \
  --display-name="MCP Mercado Publico runtime SA" \
  2>/dev/null || echo "  (already exists, skipping)"

RUNTIME_SA_EMAIL="$RUNTIME_SA@$PROJECT_ID.iam.gserviceaccount.com"

echo "  Granting roles/storage.objectAdmin..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$RUNTIME_SA_EMAIL" \
  --role="roles/storage.objectAdmin" \
  --condition=None --quiet

echo "  Granting roles/secretmanager.secretAccessor..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$RUNTIME_SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor" \
  --condition=None --quiet

echo "  Granting roles/secretmanager.secretVersionManager..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$RUNTIME_SA_EMAIL" \
  --role="roles/secretmanager.secretVersionManager" \
  --condition=None --quiet

echo "Step 5/5 — Granting Cloud Build SA permission to deploy Cloud Run..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$CB_SA" \
  --role="roles/run.admin" \
  --condition=None --quiet
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$CB_SA" \
  --role="roles/iam.serviceAccountUser" \
  --condition=None --quiet

echo ""
echo "Setup complete."
echo ""
echo "  Bucket     : gs://$GCS_BUCKET"
echo "  Runtime SA : $RUNTIME_SA_EMAIL"
echo "  AR repo    : $REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO"
echo ""
echo "Next steps:"
echo "  1. Run a first deploy to get the service URL:"
echo "     GCS_BUCKET=$GCS_BUCKET OAUTH_AUDIENCE=placeholder PROJECT_ID=$PROJECT_ID ./scripts/deploy.sh"
echo "  2. Copy the Cloud Run URL from the deploy output."
echo "  3. Re-deploy setting OAUTH_AUDIENCE to that URL."
