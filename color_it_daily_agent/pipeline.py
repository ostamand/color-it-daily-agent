import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Tuple
from fastapi import HTTPException

from color_it_daily_agent.context import (
    AgentContext,
    set_agent_context,
    VALID_TARGET_AUDIENCES,
    DEFAULT_TARGET_AUDIENCE,
)
from color_it_daily_agent.lib.firestore_config import load_firestore_input_overrides
from color_it_daily_agent.lib.collections import get_collection, DEFAULT_COLLECTION_NAME
from color_it_daily_agent.lib.micro_styles import resolve_micro_style
from color_it_daily_agent.lib.persistence import pre_create_document, get_local_output_dir

logger = logging.getLogger(__name__)


def prepare_agent_execution(input_payload: Dict[str, Any]) -> Tuple[AgentContext, Dict[str, Any]]:
    """
    Processes the raw API input payload:
    1. Normalizes payload field aliases (collection -> collection_name, keyword -> target_keyword, selected_style -> micro_style).
    2. Overrides non-null fields from Firestore config document ('coloritdaily_config/agent_input').
    3. Validates collection existence and activity.
    4. Resolves micro_style dynamically via API endpoints (fails fast on error).
    5. Normalizes target_audience (defaults to 'kids_3_10').
    6. Pre-creates a Firestore (or local if no_persist) document with status='running'.
    7. Sets up and returns the AgentContext.
    """
    merged_payload = dict(input_payload)

    # Alias normalization on input payload
    if "collection" in merged_payload and "collection_name" not in merged_payload:
        merged_payload["collection_name"] = merged_payload.get("collection")
    if "keyword" in merged_payload and "target_keyword" not in merged_payload:
        merged_payload["target_keyword"] = merged_payload.get("keyword")
    if "selected_style" in merged_payload and "micro_style" not in merged_payload:
        merged_payload["micro_style"] = merged_payload.get("selected_style")

    # 1. Load Firestore Overrides & Merge
    firestore_overrides = load_firestore_input_overrides()
    for k, v in firestore_overrides.items():
        if v is not None:
            if k == "selected_style" and "micro_style" not in firestore_overrides:
                merged_payload["micro_style"] = v
            else:
                merged_payload[k] = v
            logger.info(f"Overrode input field '{k}' with Firestore value: {v}")

    # Extract & set defaults
    current_date = merged_payload.get("current_date") or datetime.now().strftime("%Y-%m-%d")
    merged_payload["current_date"] = current_date

    collection_name = merged_payload.get("collection_name") or DEFAULT_COLLECTION_NAME
    merged_payload["collection_name"] = collection_name

    no_persist = bool(merged_payload.get("no_persist", False))
    merged_payload["no_persist"] = no_persist

    target_keyword = merged_payload.get("target_keyword")
    if target_keyword:
        target_keyword = str(target_keyword).strip()
        merged_payload["target_keyword"] = target_keyword
        logger.info(f"🎯 Target Keyword set: '{target_keyword}'")

    # 2. Validate Collection
    collection_data = get_collection(collection_name)
    if not collection_data:
        err_msg = f"Collection '{collection_name}' does not exist or is inactive."
        logger.error(err_msg)
        raise HTTPException(status_code=400, detail=err_msg)

    collection_context = collection_data.get("context")
    collection_description = collection_data.get("description")

    # 3. Resolve Micro-Style (API random selection if null/DEFAULT, or identifier lookup)
    raw_micro_style = merged_payload.get("micro_style") or merged_payload.get("selected_style")
    resolved_micro_style = resolve_micro_style(raw_micro_style, collection_name=collection_name)

    micro_style_name = resolved_micro_style.get("name")
    micro_style_unique_name = resolved_micro_style.get("unique_name")
    micro_style_description = resolved_micro_style.get("description")
    
    # Store style name & description in payload for consistent JSON logging and downstream step echoing
    merged_payload["micro_style"] = micro_style_name
    merged_payload["micro_style_description"] = micro_style_description
    logger.info(f"🎨 Micro-Style resolved: '{micro_style_name}' ({micro_style_unique_name})")

    # Extract & normalize target_audience (API Payload / Override -> Collection Doc Default -> Fallback)
    raw_audience = merged_payload.get("target_audience") or collection_data.get("target_audience")
    if raw_audience and str(raw_audience).strip().lower() in VALID_TARGET_AUDIENCES:
        target_audience = str(raw_audience).strip().lower()
    else:
        target_audience = DEFAULT_TARGET_AUDIENCE

    merged_payload["target_audience"] = target_audience
    logger.info(f"🎯 Target Audience set: '{target_audience}'")

    # 4. Generate Document ID & Pre-Create Document
    document_id = str(uuid.uuid4())
    pre_create_document(
        document_id=document_id,
        current_date=current_date,
        collection_name=collection_name,
        no_persist=no_persist,
        input_payload=merged_payload,
    )

    # 5. Create & Set Agent Context
    ctx = AgentContext(
        document_id=document_id,
        current_date=current_date,
        collection_name=collection_name,
        no_persist=no_persist,
        target_keyword=target_keyword,
        target_audience=target_audience,
        collection_context=collection_context,
        collection_description=collection_description,
        collection_data=collection_data,
        micro_style=micro_style_name,
        micro_style_name=micro_style_name,
        micro_style_unique_name=micro_style_unique_name,
        micro_style_description=micro_style_description,
        micro_style_data=resolved_micro_style,
        local_output_dir=get_local_output_dir(document_id),
    )
    set_agent_context(ctx)

    return ctx, merged_payload
