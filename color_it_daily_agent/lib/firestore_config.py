import logging
import os
from typing import Dict, Any
from color_it_daily_agent.lib.database import get_db
from color_it_daily_agent.app_configs import configs

logger = logging.getLogger(__name__)

CONFIG_FIRESTORE_COLLECTION = os.environ.get("FIRESTORE_CONFIG_COLLECTION", "coloritdaily_config")
CONFIG_FIRESTORE_DOC_ID = os.environ.get("FIRESTORE_CONFIG_DOC_ID", "agent_input")

def load_firestore_input_overrides(
    collection_name: str = CONFIG_FIRESTORE_COLLECTION,
    doc_id: str = CONFIG_FIRESTORE_DOC_ID
) -> Dict[str, Any]:
    """
    Loads configuration dictionary from Firestore document (default 'coloritdaily_config/agent_input').
    If the document does not exist or cannot be accessed, it is gracefully ignored.
    Returns a dictionary of non-null override fields.
    """
    overrides = {}
    try:
        db = get_db()
        doc_ref = db.collection(collection_name).document(doc_id).get()
        if doc_ref.exists:
            data = doc_ref.to_dict() or {}
            for k, v in data.items():
                if v is not None:
                    overrides[k] = v
            logger.info(f"Loaded {len(overrides)} input override(s) from Firestore '{collection_name}/{doc_id}'")
        else:
            logger.debug(f"Firestore config document '{collection_name}/{doc_id}' not found. Proceeding with request payload.")
    except Exception as e:
        logger.debug(f"Firestore config check skipped for '{collection_name}/{doc_id}': {e}")
        
    return overrides
