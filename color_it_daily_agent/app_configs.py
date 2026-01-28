import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Configs:
    gcp_project: str
    gcp_location: str
    llm_model: str
    media_model: str
    local_persistence: bool
    embedding_collection: str
    coloring_page_collection: str
    gcp_media_bucket: str

    @classmethod
    def from_env(cls):
        return cls(
            gcp_project=os.environ["GOOGLE_CLOUD_PROJECT"],
            gcp_location=os.environ["GOOGLE_CLOUD_LOCATION"],
            llm_model=os.environ["LLM_MODEL"],
            media_model=os.environ["MEDIA_MODEL"],
            embedding_collection=os.environ["EMBEDDING_COLLECTION"],
            coloring_page_collection=os.environ["COLORING_PAGE_COLLECTION"],
            gcp_media_bucket=os.environ["GCP_MEDIA_BUCKET"],
            local_persistence=os.environ.get("LOCAL_PERSISTENCE", "false").lower() in ('true', '1', 'yes')
        )

try:
    configs = Configs.from_env()
except KeyError as e:
    print(f"CRITICAL ERROR: Missing environment variable {e}")
    exit(1)