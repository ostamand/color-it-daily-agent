import os
import json
import logging
from typing import List, Optional
from datetime import datetime, timezone
from google.cloud.firestore_v1.vector import Vector

from google.adk.tools.tool_context import ToolContext
from ...lib.embeddings import generate_embedding
from ...lib.database import get_db
from ...lib.persistence import update_document, get_local_output_dir
from ...context import get_agent_context
from ...app_configs import configs

from ...lib.version import get_agent_version

logger = logging.getLogger(__name__)

def publish_to_firestore(
    title: str,
    reasoning: str,
    description: str,
    visual_tags: List[str],
    mood: str,
    target_audience: str,
    positive_prompt: str,
    optimized_image_path: str,
    status: str,
    feedback: str,
    micro_style: Optional[str] = None,
    micro_style_description: Optional[str] = None,
    tool_context: Optional[ToolContext] = None
) -> str:
    """
    Saves the approved coloring page metadata to Firestore (or local file if no_persist).
    """
    ctx = get_agent_context()
    
    doc_id = ctx.document_id
    collection_name = ctx.collection_name
    no_persist = ctx.no_persist
    agent_version = ctx.agent_version

    published_date = datetime.now(timezone.utc)

    resolved_micro_style_desc = micro_style_description or (ctx.micro_style_description if ctx else None)

    metadata_payload = {
        "published": False,
        "title": title,
        "reasoning": reasoning,
        "description": description,
        "visual_tags": visual_tags,
        "mood": mood,
        "target_audience": target_audience,
        "micro_style": micro_style or (ctx.micro_style_name if ctx else None),
        "micro_style_description": resolved_micro_style_desc,
        "positive_prompt": positive_prompt,
        "optimized_image_path": optimized_image_path,
        "status": status,
        "feedback": feedback,
        "collection_name": collection_name,
        "target_keyword": ctx.target_keyword if ctx else None,
        "agent_version": agent_version,
        "model_name": os.environ.get("MEDIA_MODEL"),
        "prompt_model_name": os.environ.get("LLM_MODEL"),
        "published_date": published_date.isoformat()
    }

    if no_persist:
        update_document(doc_id, metadata_payload, no_persist=True)
        logger.info(f"[NO_PERSIST] Published document metadata locally for ID {doc_id}")
        if tool_context:
            tool_context.actions.escalate = True
        return f"SUCCESS: Saved '{title}' locally to review (no_persist=True) with ID {doc_id}"

    db = get_db()
    batch = db.batch()
    new_doc_ref = db.collection(configs.coloring_page_collection).document(doc_id)

    # Generate Embedding for semantic search
    try:
        embedding_vector = generate_embedding(description, task_type="RETRIEVAL_DOCUMENT")
        if embedding_vector:
            vector_ref = db.collection(configs.embedding_collection).document(doc_id)
            vector_payload = {
                "embedding": Vector(embedding_vector),
                "published_date": published_date
            }
            batch.set(vector_ref, vector_payload, merge=True)
    except Exception as e:
        logger.warning(f"Could not generate embedding for doc '{doc_id}': {e}")

    batch.set(new_doc_ref, metadata_payload, merge=True)
    batch.commit()

    if tool_context:
        tool_context.actions.escalate = True

    return f"SUCCESS: Published '{title}' to Firestore with ID {doc_id}"

