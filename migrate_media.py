import os
import argparse
import requests
import psycopg2
from google.cloud import storage
from dotenv import load_dotenv
import logging
from urllib.parse import urlparse

# Load environment variables
load_dotenv("jobs/daily-push/.env")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Constants
BUCKET_NAME = "color-it-daily-agent-assets"
AWS_DOMAIN = "cloudfront.net"
GCS_BASE_URL = f"https://storage.googleapis.com/{BUCKET_NAME}"

# Postgres Config
PG_HOST = os.environ.get("POSTGRES_HOST")
PG_PORT = os.environ.get("POSTGRES_PORT", "5432")
PG_DB = os.environ.get("POSTGRES_DB")
PG_USER = os.environ.get("POSTGRES_USER")
PG_PASSWORD = os.environ.get("POSTGRES_PASSWORD")

def get_filename(url):
    return os.path.basename(urlparse(url).path)

def upload_to_gcs(bucket, source_url, destination_blob_name, dry_run=False):
    if dry_run:
        logger.info(f"[DRY RUN] Would download {source_url} and upload to gs://{BUCKET_NAME}/{destination_blob_name}")
        return f"{GCS_BASE_URL}/{destination_blob_name}"

    try:
        response = requests.get(source_url, stream=True)
        response.raise_for_status()
        
        blob = bucket.blob(destination_blob_name)
        # Set content type based on extension if possible, or let it be inferred
        content_type = response.headers.get('Content-Type')
        blob.upload_from_string(response.content, content_type=content_type)
        
        logger.info(f"Successfully migrated {source_url} to {GCS_BASE_URL}/{destination_blob_name}")
        return f"{GCS_BASE_URL}/{destination_blob_name}"
    except Exception as e:
        logger.error(f"Failed to migrate {source_url}: {e}")
        return None

def migrate(dry_run=False, limit=None):
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASSWORD
        )
        cursor = conn.cursor()
        
        # Query for pages that have at least one AWS URL
        query = """
            SELECT id, full_path, thumbnail_path, colored_path 
            FROM pages 
            WHERE full_path LIKE %s 
               OR thumbnail_path LIKE %s 
               OR colored_path LIKE %s
        """
        pattern = f"%{AWS_DOMAIN}%"
        cursor.execute(query, (pattern, pattern, pattern))
        
        pages = cursor.fetchall()
        
        if limit:
            pages = pages[:limit]
            
        logger.info(f"Found {len(pages)} pages to process.")
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        
        migrated_count = 0
        
        for page_id, full_path, thumbnail_path, colored_path in pages:
            logger.info(f"Processing page ID: {page_id}")
            
            updates = {}
            
            # Migrate full_path
            if full_path and AWS_DOMAIN in full_path:
                filename = get_filename(full_path)
                new_url = upload_to_gcs(bucket, full_path, f"optimized/{filename}", dry_run)
                if new_url:
                    updates["full_path"] = new_url
            
            # Migrate thumbnail_path
            if thumbnail_path and AWS_DOMAIN in thumbnail_path:
                filename = get_filename(thumbnail_path)
                new_url = upload_to_gcs(bucket, thumbnail_path, f"thumbnail/{filename}", dry_run)
                if new_url:
                    updates["thumbnail_path"] = new_url
                    
            # Migrate colored_path
            if colored_path and AWS_DOMAIN in colored_path:
                filename = get_filename(colored_path)
                new_url = upload_to_gcs(bucket, colored_path, f"colored/{filename}", dry_run)
                if new_url:
                    updates["colored_path"] = new_url
            
            if updates:
                if dry_run:
                    logger.info(f"[DRY RUN] Would update page {page_id} with: {updates}")
                else:
                    set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
                    update_query = f"UPDATE pages SET {set_clause} WHERE id = %s"
                    cursor.execute(update_query, list(updates.values()) + [page_id])
                    conn.commit()
                    logger.info(f"Updated database for page {page_id}")
                migrated_count += 1
            else:
                logger.warning(f"No updates for page {page_id}")
                
        logger.info(f"Migration completed. Total pages processed: {migrated_count}")
        
    except Exception as e:
        logger.error(f"Global error during migration: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate media from AWS to GCP")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without making changes")
    parser.add_argument("--limit", type=int, help="Limit the number of pages to process")
    
    args = parser.parse_args()
    
    migrate(dry_run=args.dry_run, limit=args.limit)
