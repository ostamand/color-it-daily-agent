#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [ -f "${ENV_FILE}" ]; then
    echo "📋 Loading environment variables from .env..."
    set -a
    source "${ENV_FILE}"
    set +a
fi

# Fallback defaults if not set in .env
GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-ostamand-264a1}"
FIRESTORE_PROJECT_ID="${FIRESTORE_PROJECT_ID:-$GOOGLE_CLOUD_PROJECT}"
GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-global}"
GOOGLE_GENAI_USE_VERTEXAI="${GOOGLE_GENAI_USE_VERTEXAI:-True}"
LLM_MODEL="${LLM_MODEL:-gemini-3-flash-preview}"
MEDIA_MODEL="${MEDIA_MODEL:-gemini-3.1-flash-image-preview}"
EMBEDDING_COLLECTION="${EMBEDDING_COLLECTION:-coloring_pages_vectors}"
COLORING_PAGE_COLLECTION="${COLORING_PAGE_COLLECTION:-coloring_pages}"
GCP_MEDIA_BUCKET="${GCP_MEDIA_BUCKET:-color-it-daily-agent-assets}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-color-it-daily-agent@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com}"
REGION="${REGION:-us-central1}"
IMAGE_TAG="${IMAGE_TAG:-us-east4-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/ostamand/color-it-daily-agent:latest}"

echo "🚀 Starting deployment for Color It Daily Agent..."
echo "Project: ${GOOGLE_CLOUD_PROJECT}"
echo "Firestore Project: ${FIRESTORE_PROJECT_ID}"
echo "Image Tag: ${IMAGE_TAG}"

echo "1. Building Docker image..."
docker build -t "${IMAGE_TAG}" -f dockerfile.agent .

echo "2. Pushing Docker image to Artifact Registry..."
docker push "${IMAGE_TAG}"

echo "3. Deploying service to GCP Cloud Run..."
gcloud run deploy color-it-daily-agent \
	--image "${IMAGE_TAG}" \
	--region "${REGION}" \
	--service-account "${SERVICE_ACCOUNT}" \
	--set-env-vars GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT}" \
	--set-env-vars FIRESTORE_PROJECT_ID="${FIRESTORE_PROJECT_ID}" \
	--set-env-vars GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION}" \
	--set-env-vars GOOGLE_GENAI_USE_VERTEXAI="${GOOGLE_GENAI_USE_VERTEXAI}" \
	--set-env-vars LLM_MODEL="${LLM_MODEL}" \
	--set-env-vars MEDIA_MODEL="${MEDIA_MODEL}" \
	--set-env-vars EMBEDDING_COLLECTION="${EMBEDDING_COLLECTION}" \
	--set-env-vars COLORING_PAGE_COLLECTION="${COLORING_PAGE_COLLECTION}" \
	--set-env-vars GCP_MEDIA_BUCKET="${GCP_MEDIA_BUCKET}" \
	--min-instances 0 \
	--max-instances 2 \
	--platform managed \
	--no-allow-unauthenticated

echo "🎉 Deployment successfully completed!"
