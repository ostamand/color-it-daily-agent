# Color It Daily Agent

An autonomous agent system designed to generate, validate, and publish high-quality coloring pages daily.

## Installation

### Prerequisites

*   Python 3.10+
*   Google Cloud Platform project with Vertex AI and Cloud Storage enabled.
*   System dependencies for image processing.

### System Dependencies

This project uses `potrace` for vectorizing images to ensure high-quality, crisp lines for printing. You must install it on your system.

**Linux (Debian/Ubuntu/Cloud Run):**
```bash
sudo apt-get update && sudo apt-get install -y potrace
```

**macOS:**
```bash
brew install potrace
```

### Python Dependencies

Install the required Python packages using pip:

```bash
pip install -r requirements.txt
```

### Configuration

1.  Copy the example environment file (if available) or create a `.env` file in the root directory.
2.  Set the required environment variables for Google Cloud:

```env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GCS_MEDIA_BUCKET=your-media-bucket-name
# Add other variables as defined in app_configs.py
```

## Running the Agent

You can run the agent locally using the provided module entry point:

```bash
python -m color_it_daily_agent.agent
```
