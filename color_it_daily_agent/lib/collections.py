import time
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from color_it_daily_agent.lib.database import get_db

logger = logging.getLogger(__name__)

COLLECTIONS_FIRESTORE_COLLECTION = "coloritdaily_collections"
DEFAULT_COLLECTION_NAME = "Wonder Daily"
DEFAULT_CREATIVE_SKILL = (
    "Thick Line Art Style Guide – "
    "Art Style: Bold, uniform black vector outlines, pure black-and-white coloring book style with no shading, gradients, or texture fills. "
    "Composition: Strong single focal point, balanced storybook framing with large closed shapes designed for children ages 3-10."
)

CACHE_TTL_SECONDS = 300  # 5 minutes in-memory cache
_COLLECTION_CACHE: Dict[str, Tuple[float, Optional[Dict[str, Any]]]] = {}

def get_collection(collection_name: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """
    Look up a collection by name in the Firestore 'collections' collection.
    Uses a 5-minute in-memory TTL cache to reduce Firestore reads.
    Checks if the collection exists and is_active is True.
    Returns the collection dict, or None if invalid/not found.
    """
    if not collection_name:
        collection_name = DEFAULT_COLLECTION_NAME

    cache_key = collection_name.lower().strip()
    now = time.time()

    if use_cache and cache_key in _COLLECTION_CACHE:
        cached_time, cached_data = _COLLECTION_CACHE[cache_key]
        if now - cached_time < CACHE_TTL_SECONDS:
            return cached_data

    result = _fetch_collection_from_db(collection_name)
    _COLLECTION_CACHE[cache_key] = (now, result)
    return result


def _fetch_collection_from_db(collection_name: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    
    # 1. Try looking up directly by document ID (slug)
    doc_ref = db.collection(COLLECTIONS_FIRESTORE_COLLECTION).document(collection_name).get()
    docs = []
    if doc_ref.exists:
        docs = [doc_ref]
    else:
        # 2. Query by field 'name'
        query = db.collection(COLLECTIONS_FIRESTORE_COLLECTION).where("name", "==", collection_name).limit(1).stream()
        docs = list(query)
        if not docs:
            # 3. Query by field 'slug'
            slug_key = collection_name.lower().strip().replace(" ", "-")
            query_slug = db.collection(COLLECTIONS_FIRESTORE_COLLECTION).where("slug", "==", slug_key).limit(1).stream()
            docs = list(query_slug)
            
    if docs:
        doc = docs[0]
        data = doc.to_dict() if hasattr(doc, "to_dict") else doc.to_dict()
        data["id"] = doc.id
        
        # Check active status (default to True if not present)
        is_active = data.get("is_active", True)
        if not is_active:
            logger.warning(f"Collection '{collection_name}' exists but is marked inactive.")
            return None
            
        if "creative_skill" not in data or not data["creative_skill"]:
            data["creative_skill"] = DEFAULT_CREATIVE_SKILL
            
        return data

    # 3. Fallback for default collection "Wonder Daily" (or "wonder_daily") if DB not yet seeded
    if collection_name.lower() in (DEFAULT_COLLECTION_NAME.lower(), "wonder_daily"):
        logger.info(f"Using default fallback configuration for collection '{collection_name}'")
        now_str = datetime.now(timezone.utc).isoformat()
        return {
            "id": "wonder-daily-default",
            "name": DEFAULT_COLLECTION_NAME,
            "description": "A fresh coloring page every day — playful, imaginative, and perfect for little hands.",
            "image_url": None,
            "is_active": True,
            "creative_skill": DEFAULT_CREATIVE_SKILL,
            "created_at": now_str,
            "updated_at": now_str,
        }

    logger.warning(f"Collection '{collection_name}' not found in Firestore.")
    return None
