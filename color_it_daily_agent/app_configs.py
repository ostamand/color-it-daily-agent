import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Configs:
    gcp_project: str
    firestore_project_id: str
    gcp_location: str
    llm_model: str
    media_model: str
    local_persistence: bool
    embedding_collection: str
    coloring_page_collection: str
    gcp_media_bucket: str

    @classmethod
    def from_env(cls):
        gcp_proj = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        firestore_proj = os.environ.get("FIRESTORE_PROJECT_ID", gcp_proj)
        media_bucket = os.environ.get("GCP_MEDIA_BUCKET", "color-it-daily-agent-assets")

        return cls(
            gcp_project=gcp_proj,
            firestore_project_id=firestore_proj,
            gcp_location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
            llm_model=os.environ.get("LLM_MODEL", "gemini-3-flash-preview"),
            media_model=os.environ.get("MEDIA_MODEL", "gemini-3.1-flash-image-preview"),
            embedding_collection=os.environ.get("EMBEDDING_COLLECTION", "coloring_pages_vectors"),
            coloring_page_collection=os.environ.get("COLORING_PAGE_COLLECTION", "coloring_pages"),
            gcp_media_bucket=media_bucket,
            local_persistence=os.environ.get("LOCAL_PERSISTENCE", "false").lower()
            in ("true", "1", "yes"),
        )


try:
    configs = Configs.from_env()
except KeyError as e:
    print(f"CRITICAL ERROR: Missing environment variable {e}")
    exit(1)
