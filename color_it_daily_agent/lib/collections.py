import os
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION_NAME = "Wonder Daily"
DEFAULT_CREATIVE_SKILL = (
    "Thick Line Art Style Guide – "
    "Art Style: Bold, uniform black vector outlines, pure black-and-white coloring book style with no shading, gradients, or texture fills. "
    "Composition: Strong single focal point, balanced storybook framing with large closed shapes designed for children ages 3-10."
)


def get_collection(collection_name: str) -> Optional[Dict[str, Any]]:
    """
    Look up a collection by name from the Public Collections API.
    Returns the collection dict, or None if invalid/not found.
    """
    if not collection_name:
        collection_name = DEFAULT_COLLECTION_NAME

    return _fetch_collection_from_api(collection_name)


def _fetch_collection_from_api(collection_name: str) -> Optional[Dict[str, Any]]:
    """
    Fetches collection metadata directly from the public collections API endpoint.
    Appends /collections to the broad API_BASE_URL.
    """
    api_base_url = os.environ.get("API_BASE_URL")
    collections_endpoint = f"{api_base_url.rstrip('/')}/collections"

    clean_target = collection_name.lower().strip()
    encoded_name = urllib.parse.quote(clean_target)

    # 1. Try single collection endpoint: GET <API_BASE_URL>/collections/:collectionName
    single_url = f"{collections_endpoint}/{encoded_name}"
    req = urllib.request.Request(
        single_url,
        headers={"User-Agent": "ColorItDailyAgent/1.0", "Accept": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                body = response.read().decode("utf-8")
                item = json.loads(body)

                if isinstance(item, dict) and (item.get("id") or item.get("unique_name") or item.get("name") or item.get("slug")):
                    logger.info(f"Loaded collection '{collection_name}' via Public API ({single_url}).")
                    return _normalize_collection_payload(item, collection_name)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            logger.debug(f"HTTP error {e.code} when requesting '{single_url}': {e}")
    except Exception as e:
        logger.debug(f"Direct API call for '{single_url}' failed: {e}")

    # 2. Try list endpoint: GET <API_BASE_URL>/collections
    req_list = urllib.request.Request(
        collections_endpoint,
        headers={"User-Agent": "ColorItDailyAgent/1.0", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req_list, timeout=5) as response:
            if response.status == 200:
                body = response.read().decode("utf-8")
                payload = json.loads(body)

                collections_list = []
                if isinstance(payload, list):
                    collections_list = payload
                elif isinstance(payload, dict):
                    if "collections" in payload and isinstance(payload["collections"], list):
                        collections_list = payload["collections"]
                    elif "data" in payload and isinstance(payload["data"], list):
                        collections_list = payload["data"]

                target_slug = clean_target.replace(" ", "-")
                for item in collections_list:
                    c_name = str(item.get("display_name") or item.get("name") or "").lower().strip()
                    c_slug = str(item.get("unique_name") or item.get("slug") or "").lower().strip()
                    c_id = str(item.get("id") or "").lower().strip()

                    if clean_target in (c_name, c_slug, c_id) or target_slug == c_slug:
                        logger.info(f"Loaded collection '{collection_name}' via Public API list ({collections_endpoint}).")
                        return _normalize_collection_payload(item, collection_name)
    except Exception as e:
        logger.debug(f"API list lookup at '{collections_endpoint}' failed: {e}")

    logger.warning(f"Collection '{collection_name}' not found via Public API ({collections_endpoint}).")
    return None


def _normalize_collection_payload(item: Dict[str, Any], requested_name: str) -> Optional[Dict[str, Any]]:
    """Normalizes collection dictionary fields returned by the API."""
    is_active = item.get("is_active", True)
    if not is_active:
        logger.warning(f"Collection '{requested_name}' is marked inactive.")
        return None

    unique_name = item.get("unique_name") or item.get("slug") or item.get("id") or requested_name
    display_name = item.get("display_name") or item.get("name") or requested_name
    description = item.get("description") or item.get("sub_heading") or item.get("heading") or ""

    return {
        "id": str(item.get("id") or unique_name),
        "name": display_name,
        "slug": unique_name,
        "unique_name": unique_name,
        "heading": item.get("heading", ""),
        "description": description,
        "context": item.get("context"),
        "image_url": item.get("image_url") or item.get("background_url"),
        "is_active": True,
        "creative_skill": item.get("creative_skill") or DEFAULT_CREATIVE_SKILL,
        "target_audience": item.get("target_audience"),
    }
