import os
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, Dict, Any, List
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _get_api_headers() -> Dict[str, str]:
    headers = {
        "User-Agent": "ColorItDailyAgent/1.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    api_key = os.environ.get("COLORITDAILY_API_KEY") or os.environ.get("API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def fetch_random_micro_style(
    collection_name: str, exclude: Optional[List[Any]] = None
) -> Dict[str, Any]:
    """
    Fetches a uniform random active micro-style for collection_name from the Public API.
    Endpoint: GET or POST /collections/:collectionName/random-micro-style

    Raises HTTPException on API failure or unexpected response (no silent fallback).
    """
    api_base_url = os.environ.get("API_BASE_URL")
    if not api_base_url:
        err_msg = "API_BASE_URL environment variable is not configured. Cannot fetch random micro-style."
        logger.error(err_msg)
        raise HTTPException(status_code=500, detail=err_msg)

    clean_collection = collection_name.strip()
    encoded_collection = urllib.parse.quote(clean_collection.lower())
    endpoint_url = f"{api_base_url.rstrip('/')}/collections/{encoded_collection}/random-micro-style"

    headers = _get_api_headers()
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
                if isinstance(payload, dict) and payload.get("success"):
                    micro_style = payload.get("micro_style")
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
    Endpoint: GET /collections/micro-styles/:slugOrId

    Raises HTTPException if not found or on API error.
    """
    api_base_url = os.environ.get("API_BASE_URL")
    if not api_base_url:
        err_msg = "API_BASE_URL environment variable is not configured. Cannot lookup micro-style."
        logger.error(err_msg)
        raise HTTPException(status_code=500, detail=err_msg)

    clean_identifier = str(identifier).strip()
    encoded_identifier = urllib.parse.quote(clean_identifier.lower().replace(" ", "-"))
    endpoint_url = f"{api_base_url.rstrip('/')}/collections/micro-styles/{encoded_identifier}"

    headers = _get_api_headers()
    req = urllib.request.Request(endpoint_url, headers=headers, method="GET")

    try:
        logger.info(f"Fetching micro-style '{identifier}' via API: {endpoint_url}")
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                body = response.read().decode("utf-8")
                payload = json.loads(body)
                if isinstance(payload, dict) and payload.get("success"):
                    micro_style = payload.get("micro_style")
                    if isinstance(micro_style, dict) and micro_style.get("name") and micro_style.get("description"):
                        logger.info(f"Successfully fetched micro-style '{micro_style.get('name')}' by identifier '{identifier}'")
                        return {
                            "id": micro_style.get("id"),
                            "name": str(micro_style.get("name")).strip(),
                            "unique_name": str(micro_style.get("unique_name") or micro_style.get("slug") or micro_style.get("name")).strip(),
                            "description": str(micro_style.get("description")).strip(),
                            "raw": micro_style,
                        }
                err_detail = f"API micro-style endpoint returned invalid response payload for '{identifier}': {body}"
                logger.error(err_detail)
                raise HTTPException(status_code=500, detail=err_detail)
            else:
                err_detail = f"API micro-style lookup for '{identifier}' returned status code {response.status}"
                logger.error(err_detail)
                raise HTTPException(status_code=response.status, detail=err_detail)
    except urllib.error.HTTPError as e:
        err_msg = f"HTTP Error {e.code} looking up micro-style '{identifier}' from {endpoint_url}: {e.reason}"
        logger.error(err_msg)
        raise HTTPException(status_code=e.code, detail=err_msg)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        err_msg = f"Failed to fetch micro-style '{identifier}' from API endpoint '{endpoint_url}': {e}"
        logger.error(err_msg)
        raise HTTPException(status_code=500, detail=err_msg)


def resolve_micro_style(
    style_input: Any, collection_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolves a micro_style payload:
    - If dict with name and description: returns normalized dict.
    - If string / int (identifier): queries GET /collections/micro-styles/:slugOrId.
    - If None / empty / "DEFAULT": queries GET /collections/:collectionName/random-micro-style.

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
