import os
import json
import logging
from typing import Dict, Any
from datetime import datetime, timezone
from color_it_daily_agent.app_configs import configs
from color_it_daily_agent.lib.database import get_db

logger = logging.getLogger(__name__)

DEFAULT_LOCAL_DIR = os.path.join(os.getcwd(), "tmp", "color_it_daily")
LOCAL_TEMP_DIR = os.environ.get("IMAGE_OUTPUT_DIR", DEFAULT_LOCAL_DIR)


def get_coloring_page_collection_name(is_user: bool = False) -> str:
    """
    Returns the target Firestore collection name for coloring pages.
    When is_user is True (or ctx.is_user is True), appends '_user' to COLORING_PAGE_COLLECTION.
    """
    base_col = configs.coloring_page_collection
    if is_user:
        return f"{base_col}_user"
    from color_it_daily_agent.context import get_agent_context
    ctx = get_agent_context()
    if ctx and ctx.is_user:
        return f"{base_col}_user"
    return base_col


def get_local_output_dir(document_id: str) -> str:
    """Returns the local output directory for a specific document run."""
    from color_it_daily_agent.context import get_agent_context
    ctx = get_agent_context()
    if ctx and ctx.local_output_dir and ctx.document_id == document_id:
        os.makedirs(ctx.local_output_dir, exist_ok=True)
        return ctx.local_output_dir

    dir_path = os.path.join(LOCAL_TEMP_DIR, document_id)
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


def pre_create_document(
    document_id: str,
    current_date: str,
    collection_name: str,
    no_persist: bool,
    input_payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Pre-creates a document with status='running' before the agent starts.
    If no_persist is True, writes to a local document.json file.
    Otherwise, writes to Firestore.
    """
    now = datetime.now(timezone.utc)
    doc_data = {
        "id": document_id,
        "status": "running",
        "current_date": current_date,
        "collection_name": collection_name,
        "no_persist": no_persist,
        "input": input_payload,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    local_dir = get_local_output_dir(document_id)
    local_doc_path = os.path.join(local_dir, "document.json")
    with open(local_doc_path, "w", encoding="utf-8") as f:
        json.dump(doc_data, f, indent=2)

    if not no_persist:
        try:
            db = get_db()
            is_user = bool(input_payload.get("user") or input_payload.get("is_user"))
            target_col = get_coloring_page_collection_name(is_user=is_user)
            doc_ref = db.collection(target_col).document(document_id)
            doc_ref.set({
                "status": "running",
                "current_date": current_date,
                "collection_name": collection_name,
                "input": input_payload,
                "created_at": now,
                "updated_at": now,
            })
            logger.info(f"Pre-created Firestore document '{document_id}' in '{target_col}' with status 'running'.")
        except Exception as e:
            logger.error(f"Failed to pre-create Firestore document '{document_id}': {e}")
    else:
        logger.info(f"[NO_PERSIST] Pre-created local document at '{local_doc_path}'.")

    return doc_data

def update_document(
    document_id: str,
    updates: Dict[str, Any],
    no_persist: bool = False
) -> None:
    """
    Updates document metadata.
    If no_persist is True, updates the local document.json.
    Otherwise, updates Firestore.
    """
    now = datetime.now(timezone.utc)
    updates["updated_at"] = now.isoformat() if no_persist else now

    local_dir = get_local_output_dir(document_id)
    local_doc_path = os.path.join(local_dir, "document.json")

    # Always keep local document.json updated
    try:
        current_local = {}
        if os.path.exists(local_doc_path):
            with open(local_doc_path, "r", encoding="utf-8") as f:
                current_local = json.load(f)
        current_local.update({
            k: (v.isoformat() if isinstance(v, datetime) else v)
            for k, v in updates.items()
        })
        with open(local_doc_path, "w", encoding="utf-8") as f:
            json.dump(current_local, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to update local document.json for '{document_id}': {e}")

    if not no_persist:
        try:
            db = get_db()
            target_col = get_coloring_page_collection_name()
            doc_ref = db.collection(target_col).document(document_id)
            doc_ref.set(updates, merge=True)
            logger.info(f"Updated Firestore document '{document_id}' in '{target_col}'.")
        except Exception as e:
            logger.error(f"Failed to update Firestore document '{document_id}': {e}")


def mark_document_failed(
    document_id: str,
    error_message: str,
    no_persist: bool = False
) -> None:
    """
    Marks a document as status='failed' with error details.
    """
    update_document(
        document_id=document_id,
        updates={
            "status": "failed",
            "error_message": error_message,
        },
        no_persist=no_persist
    )
    logger.info(f"Marked document '{document_id}' as failed (no_persist={no_persist}).")


def gcs_to_public_url(path: Any) -> Any:
    """
    Converts a gs:// bucket path into a public https://storage.googleapis.com/ URL.
    Returns non-string or non-gs:// paths unchanged.
    """
    if not path or not isinstance(path, str):
        return path
    if path.startswith("gs://"):
        return path.replace("gs://", "https://storage.googleapis.com/", 1)
    return path


def get_document_data(
    document_id: str,
    no_persist: bool = False,
    is_user: bool = False
) -> Dict[str, Any]:
    """
    Fetches full document metadata from local document.json or Firestore.
    Converts any gs:// paths (e.g. optimized_image_path) to public URLs.
    """
    doc_data = {}
    if no_persist:
        local_dir = get_local_output_dir(document_id)
        local_doc_path = os.path.join(local_dir, "document.json")
        if os.path.exists(local_doc_path):
            try:
                with open(local_doc_path, "r", encoding="utf-8") as f:
                    doc_data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to read local document.json for '{document_id}': {e}")
    else:
        try:
            db = get_db()
            target_col = get_coloring_page_collection_name(is_user=is_user)
            doc_ref = db.collection(target_col).document(document_id).get()
            if doc_ref.exists:
                doc_data = doc_ref.to_dict()
        except Exception as e:
            logger.error(f"Failed to fetch document '{document_id}': {e}")

    if doc_data and isinstance(doc_data, dict):
        if "optimized_image_path" in doc_data:
            doc_data["optimized_image_path"] = gcs_to_public_url(doc_data.get("optimized_image_path"))
        if "raw_image_path" in doc_data:
            doc_data["raw_image_path"] = gcs_to_public_url(doc_data.get("raw_image_path"))

    return doc_data or {}


def get_document_status(
    document_id: str,
    no_persist: bool = False
) -> str:
    """
    Fetches the status field of a document from Firestore or local document.json.
    """
    doc_data = get_document_data(document_id, no_persist=no_persist)
    return doc_data.get("status", "unknown")


def fetch_existing_pass_document(is_user: bool = False) -> Dict[str, Any]:
    """
    Queries Firestore for an existing document with status='PASS'.
    """
    db = get_db()
    target_col = get_coloring_page_collection_name(is_user=is_user)

    query = db.collection(target_col).where("status", "==", "PASS").limit(1).get()
    if not query:
        base_col = configs.coloring_page_collection
        if target_col != base_col:
            query = db.collection(base_col).where("status", "==", "PASS").limit(1).get()

    if query:
        return query[0].to_dict() or {}

    raise RuntimeError(f"Test mode enabled, but no existing approved ('status: PASS') document was found in Firestore collection '{target_col}'.")


def populate_test_mode_document(
    document_id: str,
    current_date: str,
    collection_name: str,
    no_persist: bool,
    input_payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Populates document metadata in test mode by fetching an existing PASS document from Firestore
    and writing it with status='PASS' for document_id.
    """
    is_user = bool(input_payload.get("user") or input_payload.get("is_user"))
    existing_doc = fetch_existing_pass_document(is_user=is_user)

    test_doc_data = dict(existing_doc)
    test_doc_data.update({
        "id": document_id,
        "status": "PASS",
        "current_date": current_date,
        "collection_name": collection_name,
        "no_persist": no_persist,
        "input": input_payload,
        "published": False,
        "published_date": datetime.now(timezone.utc).isoformat()
    })

    update_document(document_id, test_doc_data, no_persist=no_persist)
    logger.info(f"🧪 [TEST MODE] Populated document '{document_id}' with existing PASS document metadata from Firestore.")
    return test_doc_data




