# Daily Push Job

This directory contains the `daily-push` Cloud Run Function. Its primary responsibility is to migrate "published" coloring pages from Google Cloud Firestore to a PostgreSQL database.

## Project Structure

*   `main.py`: The entry point for the Cloud Run Function (`daily_push`).
*   `db_utils.py`: Helper functions for PostgreSQL database operations.
*   `deploy.sh`: Shell script to deploy the function to Google Cloud.
*   `requirements.txt`: Python package dependencies.

## Local Development & Testing

Follow these instructions to set up your local environment and test the function.

### 1. Prerequisites

*   **Python 3.10+**
*   **pip** (Python package installer)
*   **PostgreSQL**: A running instance (local or remote) with the target database and tables.
*   **Google Cloud SDK**: Installed and authenticated.

### 2. Setup

1.  **Navigate to the directory:**
    ```bash
    cd jobs/daily-push
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    Create a `.env` file in this directory with the necessary configuration. 
    **Note:** This file is ignored by git and should not be committed.

    ```env
    # Google Cloud Project ID
    GOOGLE_CLOUD_PROJECT=your-project-id
    
    # Firestore Collection Name
    COLORING_PAGE_COLLECTION=coloring_pages

    # PostgreSQL Configuration
    POSTGRES_HOST=localhost
    POSTGRES_PORT=5432
    POSTGRES_DB=your_db_name
    POSTGRES_USER=your_db_user
    POSTGRES_PASSWORD=your_db_password
    ```

5.  **Authenticate with Google Cloud:**
    Ensure your local environment has credentials to access Firestore.
    ```bash
    gcloud auth application-default login
    ```

### 3. Running Locally

Start the function using `functions-framework`. It will automatically load variables from your `.env` file.

```bash
functions-framework --target=daily_push --debug --port=8080
```

### 4. Testing

In a separate terminal window, send a POST request to trigger the function:

```bash
curl -X POST http://localhost:8080
```

*   **Success:** You should see a response like `Processed X pages.` and logs in the running function window indicating progress.
*   **No Work:** If there are no pages to process, it will return `No new pages to publish.`

## Deployment

To deploy the function to Google Cloud Run:

1.  Ensure `deploy.sh` is executable:
    ```bash
    chmod +x deploy.sh
    ```

2.  Run the deployment script (ensure you have the necessary permissions and environment variables set for the script context if needed, though the script currently expects them or hardcoded values):
    ```bash
    ./deploy.sh
    ```
