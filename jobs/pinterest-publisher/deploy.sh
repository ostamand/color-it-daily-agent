#!/bin/bash

if [ -f ".env" ]; then
  set -o allexport
  source ".env"
  set +o allexport
elif [ -f "../../.env" ]; then
  set -o allexport
  source "../../.env"
  set +o allexport
fi

FUNCTION_NAME="pinterest-publisher"
REGION="us-central1"
RUNTIME="python311"
SOURCE="."
ENTRY_POINT="pinterest_publisher"

export COLORING_PAGE_COLLECTION="${COLORING_PAGE_COLLECTION:-coloring_pages}"
export WEBSITE_BASE_URL="${WEBSITE_BASE_URL:-https://coloritdaily.com}"
export PINTEREST_GEMINI_MODEL="${PINTEREST_GEMINI_MODEL:-gemini-3.5-flash}"
export PINTEREST_ENABLED="${PINTEREST_ENABLED:-true}"
export BUFFER_ACCESS_TOKEN="${BUFFER_ACCESS_TOKEN}"
export BUFFER_PROFILE_ID="${BUFFER_PROFILE_ID}"
export PINTEREST_BOARD_ID="${PINTEREST_BOARD_ID}"
export PINTEREST_BOARD_MAP="${PINTEREST_BOARD_MAP:-{}}"
export FIRESTORE_PROJECT_ID="${FIRESTORE_PROJECT_ID}"
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT}"

export SERVICE_ACCOUNT="coloritdaily-pinterest-sa@coloring-pages-476315.iam.gserviceaccount.com"

echo "Deploying Cloud Run function: $FUNCTION_NAME..."

gcloud functions deploy $FUNCTION_NAME \
  --gen2 \
  --region=$REGION \
  --runtime=$RUNTIME \
  --source=$SOURCE \
  --entry-point=$ENTRY_POINT \
  --trigger-http \
  --max-instances=2 \
  --service-account="$SERVICE_ACCOUNT" \
  --set-env-vars GOOGLE_CLOUD_PROJECT="$GOOGLE_CLOUD_PROJECT",COLORING_PAGE_COLLECTION="$COLORING_PAGE_COLLECTION",WEBSITE_BASE_URL="$WEBSITE_BASE_URL",PINTEREST_GEMINI_MODEL="$PINTEREST_GEMINI_MODEL",PINTEREST_ENABLED="$PINTEREST_ENABLED",BUFFER_ACCESS_TOKEN="$BUFFER_ACCESS_TOKEN",BUFFER_PROFILE_ID="$BUFFER_PROFILE_ID",PINTEREST_BOARD_ID="$PINTEREST_BOARD_ID",PINTEREST_BOARD_MAP="$PINTEREST_BOARD_MAP",FIRESTORE_PROJECT_ID="$FIRESTORE_PROJECT_ID"\
  --no-allow-unauthenticated

echo "Deployment complete."
