import os
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, Dict, Any, List
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _get_api_headers(has_body: bool = False) -> Dict[str, str]:
    headers = {
        "User-Agent": "ColorItDailyAgent/1.0",
        "Accept": "application/json",
    }
    if has_body:
        headers["Content-Type"] = "application/json"
    api_key = os.environ.get("COLORITDAILY_API_KEY") or os.environ.get("API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def fetch_random_micro_style(
    collection_name: str, exclude: Optional[List[Any]] = None
) -> Dict[str, Any]:
    """
    Fetches a uniform random active micro-style for collection_name from the Public API.
    Endpoint: GET or POST /admin/collections/:collectionName/random-micro-style

    Raises HTTPException on API failure or unexpected response (no silent fallback).
    """
    api_base_url = os.environ.get("API_BASE_URL")
    if not api_base_url:
        err_msg = "API_BASE_URL environment variable is not configured. Cannot fetch random micro-style."
        logger.error(err_msg)
        raise HTTPException(status_code=500, detail=err_msg)

    clean_collection = collection_name.strip()
    encoded_collection = urllib.parse.quote(clean_collection.lower())
    endpoint_url = f"{api_base_url.rstrip('/')}/admin/collections/{encoded_collection}/random-micro-style"

    headers = _get_api_headers(has_body=bool(exclude))
    req_data = None
    method = "GET"
    if exclude:
        method = "POST"
        req_data = json.dumps({"exclude": exclude}).encode("utf-8")

    req = urllib.request.Request(
        endpoint_url, data=req_data, headers=headers, method=method
    )

    try:
        logger.info(f"Fetching random micro-style for collection '{collection_name}' via API: {endpoint_url}")
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                body = response.read().decode("utf-8")
                payload = json.loads(body)
                micro_style = None
                if isinstance(payload, dict):
                    if payload.get("micro_style") and isinstance(payload["micro_style"], dict):
                        micro_style = payload["micro_style"]
                    elif payload.get("success") and isinstance(payload.get("micro_style"), dict):
                        micro_style = payload["micro_style"]
                    elif payload.get("name") and payload.get("description"):
                        micro_style = payload

                if isinstance(micro_style, dict) and micro_style.get("name") and micro_style.get("description"):
                    logger.info(
                        f"Successfully fetched random micro-style '{micro_style.get('name')}' for collection '{collection_name}'"
                    )
                    return {
                        "id": micro_style.get("id"),
                        "name": str(micro_style.get("name")).strip(),
                        "unique_name": str(micro_style.get("unique_name") or micro_style.get("slug") or micro_style.get("name")).strip(),
                        "description": str(micro_style.get("description")).strip(),
                        "raw": micro_style,
                    }
                err_detail = f"API random-micro-style endpoint returned invalid response payload: {body}"
                logger.error(err_detail)
                raise HTTPException(status_code=500, detail=err_detail)
            else:
                err_detail = f"API random-micro-style endpoint returned status code {response.status}"
                logger.error(err_detail)
                raise HTTPException(status_code=response.status, detail=err_detail)
    except urllib.error.HTTPError as e:
        err_msg = f"HTTP Error {e.code} fetching random micro-style for '{collection_name}' from {endpoint_url}: {e.reason}"
        logger.error(err_msg)
        raise HTTPException(status_code=e.code, detail=err_msg)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        err_msg = f"Failed to fetch random micro-style from API endpoint '{endpoint_url}': {e}"
        logger.error(err_msg)
        raise HTTPException(status_code=500, detail=err_msg)


def fetch_micro_style_by_identifier(identifier: str) -> Dict[str, Any]:
    """
    Fetches a single micro-style record by its unique_name (slug), name, or numeric ID.
    Endpoint: GET /admin/micro-styles/:id (for numeric ID) or GET /admin/micro-styles (for slug/name lookup)

    Raises HTTPException if not found or on API error.
    """
    api_base_url = os.environ.get("API_BASE_URL")
    if not api_base_url:
        err_msg = "API_BASE_URL environment variable is not configured. Cannot lookup micro-style."
        logger.error(err_msg)
        raise HTTPException(status_code=500, detail=err_msg)

    clean_identifier = str(identifier).strip()
    clean_lower = clean_identifier.lower()
    clean_slug = clean_lower.replace(" ", "-")

    # If identifier is numeric (e.g. "1"), query direct GET /admin/micro-styles/:id endpoint
    if clean_identifier.isdigit():
        encoded_identifier = urllib.parse.quote(clean_identifier)
        endpoint_url = f"{api_base_url.rstrip('/')}/admin/micro-styles/{encoded_identifier}"
        headers = _get_api_headers()
        req = urllib.request.Request(endpoint_url, headers=headers, method="GET")

        try:
            logger.info(f"Fetching micro-style by ID '{identifier}' via API: {endpoint_url}")
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    body = response.read().decode("utf-8")
                    payload = json.loads(body)
                    micro_style = None
                    if isinstance(payload, dict):
                        if payload.get("micro_style") and isinstance(payload["micro_style"], dict):
                            micro_style = payload["micro_style"]
                        elif payload.get("name") and payload.get("description"):
                            micro_style = payload
                    elif isinstance(payload, list) and len(payload) > 0:
                        micro_style = payload[0]

                    if isinstance(micro_style, dict) and micro_style.get("name") and micro_style.get("description"):
                        logger.info(f"Successfully fetched micro-style '{micro_style.get('name')}' by ID '{identifier}'")
                        return {
                            "id": micro_style.get("id"),
                            "name": str(micro_style.get("name")).strip(),
                            "unique_name": str(micro_style.get("unique_name") or micro_style.get("slug") or micro_style.get("name")).strip(),
                            "description": str(micro_style.get("description")).strip(),
                            "raw": micro_style,
                        }
        except Exception as e:
            logger.debug(f"Direct ID lookup at '{endpoint_url}' failed: {e}. Falling back to list search.")

    # For string slugs/names (or if ID lookup failed), search list from GET /admin/micro-styles
    all_styles = fetch_all_micro_styles()
    for style in all_styles:
        s_id = str(style.get("id") or "").strip().lower()
        s_name = str(style.get("name") or "").strip().lower()
        s_unique = str(style.get("unique_name") or style.get("slug") or "").strip().lower()
        raw = style.get("raw") or {}
        s_slug = str(raw.get("slug") or "").strip().lower()

        if clean_lower in (s_id, s_name, s_unique, s_slug) or clean_slug in (s_unique, s_slug):
            logger.info(f"Successfully resolved micro-style '{style.get('name')}' by identifier '{identifier}' from list")
            return style

    err_detail = f"Micro-style with identifier '{identifier}' not found via API."
    logger.error(err_detail)
    raise HTTPException(status_code=404, detail=err_detail)


def fetch_all_micro_styles() -> List[Dict[str, Any]]:
    """
    Fetches all micro-styles from the consolidated admin endpoint.
    Endpoint: GET /admin/micro-styles

    Returns a top-level list of micro-style dictionaries.
    """
    api_base_url = os.environ.get("API_BASE_URL")
    if not api_base_url:
        err_msg = "API_BASE_URL environment variable is not configured. Cannot list micro-styles."
        logger.error(err_msg)
        raise HTTPException(status_code=500, detail=err_msg)

    endpoint_url = f"{api_base_url.rstrip('/')}/admin/micro-styles"
    headers = _get_api_headers()
    req = urllib.request.Request(endpoint_url, headers=headers, method="GET")

    try:
        logger.info(f"Fetching all micro-styles via API: {endpoint_url}")
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                body = response.read().decode("utf-8")
                payload = json.loads(body)
                items = []
                if isinstance(payload, list):
                    items = payload
                elif isinstance(payload, dict):
                    if isinstance(payload.get("micro_styles"), list):
                        items = payload["micro_styles"]
                    elif isinstance(payload.get("data"), list):
                        items = payload["data"]

                result = []
                for item in items:
                    if isinstance(item, dict) and item.get("name"):
                        result.append({
                            "id": item.get("id"),
                            "name": str(item.get("name")).strip(),
                            "unique_name": str(item.get("unique_name") or item.get("slug") or item.get("name")).strip(),
                            "description": str(item.get("description") or "").strip(),
                            "is_active": item.get("is_active", True),
                            "raw": item,
                        })
                logger.info(f"Successfully fetched {len(result)} micro-styles from {endpoint_url}")
                return result
            else:
                err_detail = f"API list micro-styles endpoint returned status code {response.status}"
                logger.error(err_detail)
                raise HTTPException(status_code=response.status, detail=err_detail)
    except urllib.error.HTTPError as e:
        err_msg = f"HTTP Error {e.code} listing micro-styles from {endpoint_url}: {e.reason}"
        logger.error(err_msg)
        raise HTTPException(status_code=e.code, detail=err_msg)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        err_msg = f"Failed to list micro-styles from API endpoint '{endpoint_url}': {e}"
        logger.error(err_msg)
        raise HTTPException(status_code=500, detail=err_msg)


def fetch_collection_micro_styles(collection_slug: str) -> List[Dict[str, Any]]:
    """
    Fetches micro-styles associated with a given collection slug.
    Endpoint: GET /admin/collections/:slug/micro-styles

    Returns a top-level list of micro-style dictionaries.
    """
    api_base_url = os.environ.get("API_BASE_URL")
    if not api_base_url:
        err_msg = "API_BASE_URL environment variable is not configured. Cannot fetch collection micro-styles."
        logger.error(err_msg)
        raise HTTPException(status_code=500, detail=err_msg)

    clean_slug = collection_slug.strip().lower().replace(" ", "-")
    encoded_slug = urllib.parse.quote(clean_slug)
    endpoint_url = f"{api_base_url.rstrip('/')}/admin/collections/{encoded_slug}/micro-styles"

    headers = _get_api_headers()
    req = urllib.request.Request(endpoint_url, headers=headers, method="GET")

    try:
        logger.info(f"Fetching micro-styles for collection '{collection_slug}' via API: {endpoint_url}")
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                body = response.read().decode("utf-8")
                payload = json.loads(body)
                items = []
                if isinstance(payload, list):
                    items = payload
                elif isinstance(payload, dict):
                    if isinstance(payload.get("micro_styles"), list):
                        items = payload["micro_styles"]
                    elif isinstance(payload.get("data"), list):
                        items = payload["data"]

                result = []
                for item in items:
                    if isinstance(item, dict) and item.get("name"):
                        result.append({
                            "id": item.get("id"),
                            "name": str(item.get("name")).strip(),
                            "unique_name": str(item.get("unique_name") or item.get("slug") or item.get("name")).strip(),
                            "description": str(item.get("description") or "").strip(),
                            "is_active": item.get("is_active", True),
                            "raw": item,
                        })
                logger.info(f"Successfully fetched {len(result)} micro-styles for collection '{collection_slug}'")
                return result
            else:
                err_detail = f"API collection micro-styles endpoint returned status code {response.status}"
                logger.error(err_detail)
                raise HTTPException(status_code=response.status, detail=err_detail)
    except urllib.error.HTTPError as e:
        err_msg = f"HTTP Error {e.code} fetching micro-styles for collection '{collection_slug}' from {endpoint_url}: {e.reason}"
        logger.error(err_msg)
        raise HTTPException(status_code=e.code, detail=err_msg)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        err_msg = f"Failed to fetch micro-styles for collection '{collection_slug}' from API endpoint '{endpoint_url}': {e}"
        logger.error(err_msg)
        raise HTTPException(status_code=500, detail=err_msg)


def resolve_micro_style(
    style_input: Any, collection_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolves a micro_style payload:
    - If dict with name and description: returns normalized dict.
    - If string / int (identifier): queries GET /admin/micro-styles/:id.
    - If None / empty / "DEFAULT": queries GET or POST /admin/collections/:collectionName/random-micro-style.

    If resolution fails or API error occurs, raises HTTPException.
    """
    if isinstance(style_input, dict):
        name = style_input.get("name")
        description = style_input.get("description")
        unique_name = style_input.get("unique_name") or style_input.get("slug") or name
        if name and description:
            return {
                "id": style_input.get("id"),
                "name": str(name).strip(),
                "unique_name": str(unique_name).strip() if unique_name else str(name).strip(),
                "description": str(description).strip(),
                "raw": style_input,
            }

    if style_input is not None:
        style_str = str(style_input).strip()
        if style_str and style_str.upper() != "DEFAULT":
            return fetch_micro_style_by_identifier(style_str)

    # If None, empty, or "DEFAULT", fetch random micro-style for collection
    if not collection_name:
        from color_it_daily_agent.lib.collections import DEFAULT_COLLECTION_NAME
        collection_name = DEFAULT_COLLECTION_NAME

    return fetch_random_micro_style(collection_name)

