import os
import argparse
import logging
from datetime import datetime
try:
    import functions_framework
except ImportError:
    functions_framework = None
from google.cloud import firestore
from dotenv import load_dotenv

from pinterest_publisher import publish_to_pinterest_safely, slugify

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
FIRESTORE_PROJECT_ID = os.environ.get("FIRESTORE_PROJECT_ID", os.environ.get("GOOGLE_CLOUD_PROJECT"))
COLORING_PAGE_COLLECTION = os.environ.get("COLORING_PAGE_COLLECTION", "coloring_pages")

def run_publisher(dry_run: bool = False, doc_id: str = None, limit: int = 1, force: bool = False):
    """
    Core publishing function. Can be called via Cloud Run Function HTTP request or local CLI.
    """
    try:
        db_firestore = firestore.Client(project=FIRESTORE_PROJECT_ID)
        collection_ref = db_firestore.collection(COLORING_PAGE_COLLECTION)

        if doc_id:
            # Targeted single document processing
            doc_ref = collection_ref.document(doc_id)
            doc_snap = doc_ref.get()
            if not doc_snap.exists:
                logger.error(f"Document {doc_id} not found in collection {COLORING_PAGE_COLLECTION}.")
                return f"Error: Document {doc_id} not found.", 404
            eligible_docs = [doc_snap]
        else:
            # Query for pages published on website
            query = collection_ref.where("published", "==", True)
            docs = list(query.stream())

            if not docs:
                logger.info("No published pages found in Firestore.")
                return "No published pages found.", 200

            # Filter out pages that were already published to Pinterest unless --force is set
            eligible_docs = []
            for doc in docs:
                data = doc.to_dict()
                if force or data.get("pinterest_published") is not True:
                    eligible_docs.append(doc)

            if not eligible_docs:
                logger.info("All published pages have already been posted to Pinterest.")
                return "No new pages pending Pinterest publication.", 200

            # Sort by latest published_date (or created_at) descending
            def get_sort_key(doc):
                data = doc.to_dict()
                val = data.get("published_date") or data.get("created_at")
                if isinstance(val, datetime):
                    return val.timestamp()
                return 0

            eligible_docs.sort(key=get_sort_key, reverse=True)
            if limit > 0:
                eligible_docs = eligible_docs[:limit]

        logger.info(f"Processing {len(eligible_docs)} page(s) (dry_run={dry_run}, force={force})...")

        processed_count = 0

        for doc in eligible_docs:
            data = doc.to_dict()
            target_id = doc.id
            title = data.get("title") or data.get("name") or "Untitled"

            logger.info(f"Processing candidate: {target_id} ('{title}')")

            # Transform image path to public URL
            optimized_path = data.get("optimized_image_path", "")
            if not optimized_path:
                logger.warning(f"Skipping {target_id}: Missing optimized_image_path")
                continue

            full_path_gs = optimized_path.replace(".png", ".webp")
            full_path = full_path_gs.replace("gs://", "https://storage.googleapis.com/") if full_path_gs.startswith("gs://") else full_path_gs

            page_data = dict(data)
            page_data["title"] = title
            page_data["description"] = data.get("description") or data.get("prompt") or ""
            page_data["visual_tags"] = data.get("visual_tags") or data.get("tags") or []
            page_data["unique_name"] = data.get("unique_name") or slugify(title)
            page_data["optimized_image_path"] = full_path

            # Execute safe Pinterest publication
            p_res = publish_to_pinterest_safely(target_id, page_data, dry_run=dry_run)

            status = p_res.get("status", "")
            is_success = status in ("success", "success_buffer", "success_webhook", "dry_run")

            if is_success:
                if not dry_run:
                    doc.reference.update({
                        "pinterest_published": True,
                        "pinterest_pin_id": p_res.get("pin_id"),
                        "pinterest_status": p_res.get("status"),
                        "pinterest_published_at": datetime.now(),
                        "pinterest_metadata": p_res.get("metadata")
                    })
                processed_count += 1
                logger.info(f"Completed {target_id}: {status}")
            else:
                if not dry_run:
                    doc.reference.update({
                        "pinterest_published": False,
                        "pinterest_error": p_res.get("message") or p_res.get("error")
                    })
                logger.error(f"Failed {target_id}: {p_res.get('message') or p_res.get('error')}")

        status_msg = f"Processed {processed_count} page(s) (dry_run={dry_run})."
        return status_msg, 200

    except Exception as e:
        logger.error(f"Global error in pinterest_publisher: {e}")
        return f"Error: {e}", 500


if functions_framework:
    @functions_framework.http
    def pinterest_publisher(request):
        """HTTP Cloud Function entrypoint."""
        return run_publisher()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Color It Daily - Pinterest Publisher Local CLI & Testing Tool")
    parser.add_argument("--dry-run", action="store_true", help="Simulate Pin creation without calling Pinterest API or mutating Firestore")
    parser.add_argument("--doc-id", type=str, default=None, help="Target a specific Firestore Document ID")
    parser.add_argument("--limit", type=int, default=1, help="Max number of candidate pages to process (default: 1)")
    parser.add_argument("--force", action="store_true", help="Ignore pinterest_published flag for local testing")

    args = parser.parse_args()

    print(f"\n🚀 Running Pinterest Publisher CLI (dry_run={args.dry_run}, doc_id={args.doc_id}, limit={args.limit}, force={args.force})...\n")
    msg, code = run_publisher(dry_run=args.dry_run, doc_id=args.doc_id, limit=args.limit, force=args.force)
    print(f"\nResult [{code}]: {msg}\n")
