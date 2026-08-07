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
            doc_ref = db.collection(configs.coloring_page_collection).document(document_id)
            doc_ref.set({
                "status": "running",
                "current_date": current_date,
                "collection_name": collection_name,
                "input": input_payload,
                "created_at": now,
                "updated_at": now,
            })
            logger.info(f"Pre-created Firestore document '{document_id}' with status 'running'.")
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
            doc_ref = db.collection(configs.coloring_page_collection).document(document_id)
            doc_ref.set(updates, merge=True)
            logger.info(f"Updated Firestore document '{document_id}'.")
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


def get_document_status(
    document_id: str,
    no_persist: bool = False
) -> str:
    """
    Fetches the status field of a document from Firestore or local document.json.
    """
    if no_persist:
        local_dir = get_local_output_dir(document_id)
        local_doc_path = os.path.join(local_dir, "document.json")
        if os.path.exists(local_doc_path):
            try:
                with open(local_doc_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("status", "unknown")
            except Exception as e:
                logger.error(f"Failed to read local document.json for '{document_id}': {e}")
        return "unknown"
    else:
        try:
            db = get_db()
            doc_ref = db.collection(configs.coloring_page_collection).document(document_id).get()
            if doc_ref.exists:
                return doc_ref.to_dict().get("status", "unknown")
        except Exception as e:
            logger.error(f"Failed to fetch document status for '{document_id}': {e}")
        return "unknown"


