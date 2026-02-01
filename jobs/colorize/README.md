# Colorize Cloud Function

This Cloud Function triggers when a new thumbnail is uploaded to the `optimized/thumbnail/` folder in the GCS bucket. It:
1. Identifies the image ID.
2. Fetches metadata from Firestore (`coloring_pages` collection).
3. Sends the corresponding raw image and a style-aware prompt to Gemini.
4. Saves the returned colored image to `optimized/colored/`.
5. Updates the Firestore document with the new `colored_image_path`.

## Prerequisites

- Python 3.11+
- `gcloud` CLI installed and authenticated.
- Access to the GCP Project, Firestore, and GCS.

## Local Setup

1. **Create Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configuration:**
   Create a `.env` file in this directory with the following variables:
   ```env
   GOOGLE_CLOUD_PROJECT=your-project-id
   COLORING_PAGE_COLLECTION=coloring_pages
   GCP_LOCATION=us-central1
   MODEL_NAME=gemini-2.0-flash-exp
   
   # Deployment Config
   SERVICE_ACCOUNT_EMAIL=your-service-account@your-project.iam.gserviceaccount.com
   ```

## IAM Roles & Permissions

To run this function securely, create a dedicated Service Account and grant it the following roles:

1.  **Cloud Datastore User** (`roles/datastore.user`)
    *   Required to read metadata from the `coloring_pages` Firestore collection.
2.  **Storage Object Admin** (`roles/storage.objectAdmin`)
    *   Required to read the trigger thumbnail and raw image, and write the final colored image.
3.  **Vertex AI User** (`roles/aiplatform.user`)
    *   Required to call the Gemini API for image generation.
4.  **Logs Writer** (`roles/logging.logWriter`)
    *   Required to write logs to Cloud Logging.
5.  **Eventarc Event Receiver** (`roles/eventarc.eventReceiver`)
    *   Required for the function to receive events from Cloud Storage (Eventarc).

### Creating the Service Account

```bash
# 1. Create Service Account
gcloud iam service-accounts create colorize-worker-sa \
    --display-name="Colorize Worker Service Account"

# 2. Grant Roles (Replace variables accordingly)
PROJECT_ID=$(gcloud config get-value project)
SA_EMAIL="colorize-worker-sa@${PROJECT_ID}.iam.gserviceaccount.com"
CURRENT_USER=$(gcloud config get-value account)

# Grant roles to the Service Account itself
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:${SA_EMAIL}" --role="roles/datastore.user"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:${SA_EMAIL}" --role="roles/storage.objectAdmin"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:${SA_EMAIL}" --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:${SA_EMAIL}" --role="roles/logging.logWriter"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:${SA_EMAIL}" --role="roles/eventarc.eventReceiver"

# IMPORTANT: Grant YOURSELF permission to "act as" this Service Account for deployment
gcloud iam service-accounts add-iam-policy-binding ${SA_EMAIL} \
    --member="user:${CURRENT_USER}" \
    --role="roles/iam.serviceAccountUser"
```

## Testing

### 1. Local Testing
Start Functions Framework:
```bash
functions-framework --target=colorize_image --signature-type=cloudevent --debug
```

In a separate terminal, send the mock event:
```bash
curl -X POST localhost:8080 \
  -H "Content-Type: application/cloudevents+json" \
  -d @mock_event.json
```

### 2. Deployed Function Testing
Once deployed, you can trigger the function manually using the provided script. This script fetches the service URL and handles authentication:

```bash
./test_deployed.sh
```

## Deployment

To deploy to Google Cloud Functions (Gen 2), run the deployment script:

```bash
./deploy.sh
```

Ensure your `.env` file is populated, as the script reads environment variables from it.