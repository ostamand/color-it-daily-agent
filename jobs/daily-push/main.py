import os
import logging
import functions_framework
from google.cloud import firestore
import psycopg2
from dotenv import load_dotenv
from db_utils import add_new_page

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment Variables
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
COLORING_PAGE_COLLECTION = os.environ.get("COLORING_PAGE_COLLECTION", "coloring_pages")

# Postgres Config
PG_HOST = os.environ.get("POSTGRES_HOST")
PG_PORT = os.environ.get("POSTGRES_PORT", "5432")
PG_DB = os.environ.get("POSTGRES_DB")
PG_USER = os.environ.get("POSTGRES_USER")
PG_PASSWORD = os.environ.get("POSTGRES_PASSWORD")

@functions_framework.http
def daily_push(request):
    """
    Cloud Run Function triggered via HTTP (e.g. by Cloud Scheduler).
    Migrates 'published=False' pages from Firestore to Postgres.
    """
    try:
        # 1. Initialize Firestore
        db_firestore = firestore.Client(project=PROJECT_ID)
        collection_ref = db_firestore.collection(COLORING_PAGE_COLLECTION)
        
        # Query for unpublished pages
        query = collection_ref.where("published", "==", False)
        docs = list(query.stream())
        
        if not docs:
            logger.info("No unpublished pages found.")
            return "No new pages to publish.", 200

        logger.info(f"Found {len(docs)} pages to process.")

        # 2. Connect to Postgres
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASSWORD
        )
        cursor = conn.cursor()

        processed_count = 0
        
        try:
            for doc in docs:
                data = doc.to_dict()
                doc_id = doc.id
                title = data.get("title", "Untitled")
                
                logger.info(f"Processing doc {doc_id}: {title}")

                # 3. Transform Data
                optimized_path = data.get("optimized_image_path", "")
                if not optimized_path:
                    logger.warning(f"Skipping {doc_id}: Missing optimized_image_path")
                    continue
                
                # Path transformation:
                full_path_gs = optimized_path.replace(".png", ".webp")
                thumbnail_path_gs = optimized_path.replace(".png", ".webp").replace("/optimized/", "/optimized/thumbnail/")

                # Convert to public URLs (https://storage.googleapis.com/bucket/path)
                full_path = full_path_gs.replace("gs://", "https://storage.googleapis.com/") if full_path_gs.startswith("gs://") else full_path_gs
                thumbnail_path = thumbnail_path_gs.replace("gs://", "https://storage.googleapis.com/") if thumbnail_path_gs.startswith("gs://") else thumbnail_path_gs

                page_data = {
                    "name": title,
                    "prompt": data.get("description", ""),
                    "tags": data.get("visual_tags", []),
                    "generated_on": data.get("published_date", data.get("created_at")),
                    "width": 2550,
                    "height": 3300,
                    "prompt_model_name": "gemini-3-pro-image-preview",
                    "model_name": "color-it-daily-agent-v1",
                    "generate_script": "color_it_daily_agent.agent",
                    "colored_path": None,
                    "full_path": full_path,
                    "thumbnail_path": thumbnail_path,
                }

                # 4. Insert into Postgres
                try:
                    add_new_page(cursor, page_data)
                    conn.commit() # Commit per page to ensure partial progress is saved? 
                    # Deno script does transaction per item. 
                    # If I commit here, I should update Firestore immediately.
                    
                    # 5. Update Firestore
                    doc.reference.update({"published": True})
                    
                    processed_count += 1
                    logger.info(f"Successfully published {doc_id}")
                    
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Failed to publish {doc_id}: {e}")
                    # Continue to next doc
                    continue
                    
        finally:
            cursor.close()
            conn.close()

        return f"Processed {processed_count} pages.", 200

    except Exception as e:
        logger.error(f"Global error: {e}")
        return f"Error: {e}", 500
