# Generate Thumbnail Cloud Function

This Cloud Run Function (2nd Gen) automatically generates a 4x smaller WebP thumbnail when a new image is added to the `optimized/` directory of your configured Cloud Storage bucket.

## Prerequisites

-   Google Cloud Project
-   `gcloud` CLI installed and authenticated
-   Python 3.10+

## Local Development & Testing

You can test the function locally using `functions-framework`.

1.  **Install dependencies**:
    It is recommended to use a virtual environment.
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Run the function**:
    ```bash
    functions-framework --target=generate_thumbnail --signature-type=cloudevent
    ```

3.  **Simulate an Event**:
    In a separate terminal, send a mock CloudEvent via curl. Replace `color-it-daily-agent-assets` and `YOUR_IMAGE.webp` with actual values if testing against real GCS access (which requires credentials), or just to verify the logic flow.
    
    *Note: To actually download/upload files, your local environment needs Application Default Credentials (`gcloud auth application-default login`).*

    ```bash
    curl -X POST localhost:8080 \
       -H "Content-Type: application/cloudevent+json" \
       -d 
         "{
           \"specversion\": \"1.0\",
           \"type\": \"google.cloud.storage.object.v1.finalized\",
           \"source\": \"//storage.googleapis.com/projects/_/buckets/color-it-daily-agent-assets\",
           \"id\": \"1234567890\",
           \"data\": {
             \"bucket\": \"color-it-daily-agent-assets\",
             \"name\": \"optimized/test-image.webp\",
             \"metageneration\": \"1\",
             \"timeCreated\": \"2023-10-01T00:00:00.000Z\",
             \"updated\": \"2023-10-01T00:00:00.000Z\"
           }
         }"
    ```

## GCP Deployment & Setup

### 1. Enable Required APIs
Ensure the following APIs are enabled in your Google Cloud Console:
-   Cloud Run Admin API
-   Cloud Functions API
-   Cloud Build API
-   Eventarc API
-   Cloud Pub/Sub API (used by Eventarc)
-   Cloud Logging API

You can enable them via the console or CLI:
```bash
gcloud services enable \
  run.googleapis.com \
  cloudfunctions.googleapis.com \
  cloudbuild.googleapis.com \
  eventarc.googleapis.com \
  pubsub.googleapis.com \
  logging.googleapis.com
```

### 2. Prepare the Bucket
Ensure your target bucket exists (e.g., `color-it-daily-agent-assets`).
The function expects images to be uploaded to the `optimized/` path.
*Note: The function explicitly ignores files in `thumbnail/` to prevent infinite loops.*

### 3. Grant Permissions
The Cloud Function's service account (usually the default compute service account) needs permissions to read and write to your bucket.
-   **Role**: Storage Object Admin (or at least Storage Object Viewer + Storage Object Creator)

### 4. Deploy the Function

Run the following command from this directory (`jobs/generate-thumbnail`).

Replace `[YOUR_REGION]` (e.g., `us-central1`) and `[color-it-daily-agent-assets]` with your specific values.

```bash
gcloud functions deploy generate-thumbnail \
    --gen2 \
    --runtime=python310 \
    --region='us-central1' \
    --source=. \
    --entry-point=generate_thumbnail \
    --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
    --trigger-event-filters="bucket=[color-it-daily-agent-assets]"
```

*Note: While we filter by bucket here, Cloud Functions Gen 2 (Eventarc) triggers for Storage do not currently support path-based filtering (like `prefix=optimized/`) directly in the trigger configuration for all bucket types easily without Cloud Audit Logs. **However**, the code in `main.py` explicitly checks if the file is in `optimized/` and NOT in `thumbnail/` before processing to ensure safety and correctness.*

### 5. Verification
1.  Upload an image to your bucket: `gs://[color-it-daily-agent-assets]/optimized/test.webp`
2.  Check the logs:
    ```bash
    gcloud functions logs read generate-thumbnail --region=[YOUR_REGION] --limit=10
    ```
3.  Verify the thumbnail exists at `gs://[color-it-daily-agent-assets]/optimized/thumbnail/test.webp`.