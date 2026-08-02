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

REGION="${REGION:-us-central1}"

echo "🚀 Starting deployment for Color It Daily Agent..."
echo "Project: ${GOOGLE_CLOUD_PROJECT}"
echo "Firestore Project: ${FIRESTORE_PROJECT_ID}"
echo "Image Tag: ${AGENT_IMAGE_TAG}"

echo "1. Building Docker image..."
docker build -t "${AGENT_IMAGE_TAG}" -f dockerfile.agent .

echo "2. Pushing Docker image to Artifact Registry..."
docker push "${AGENT_IMAGE_TAG}"

echo "3. Deploying service to GCP Cloud Run..."
gcloud run deploy color-it-daily-agent \
	--image "${AGENT_IMAGE_TAG}" \
	--region "${REGION}" \
	--service-account "${AGENT_SERVICE_ACCOUNT}" \
	--set-env-vars GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT}" \
	--set-env-vars FIRESTORE_PROJECT_ID="${FIRESTORE_PROJECT_ID}" \
	--set-env-vars GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION}" \
	--set-env-vars GOOGLE_GENAI_USE_VERTEXAI="${GOOGLE_GENAI_USE_VERTEXAI}" \
	--set-env-vars LLM_MODEL="${LLM_MODEL}" \
	--set-env-vars MEDIA_MODEL="${MEDIA_MODEL}" \
	--set-env-vars EMBEDDING_COLLECTION="${EMBEDDING_COLLECTION}" \
	--set-env-vars COLORING_PAGE_COLLECTION="${COLORING_PAGE_COLLECTION}" \
	--set-env-vars GCP_MEDIA_BUCKET="${GCP_MEDIA_BUCKET}" \
	--set-env-vars API_BASE_URL="${API_BASE_URL}" \
	--min-instances 0 \
	--max-instances 2 \
	--platform managed \
	--no-allow-unauthenticated

echo "🎉 Deployment successfully completed!"
