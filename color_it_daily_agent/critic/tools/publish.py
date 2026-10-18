import os
import json
import logging
from typing import List, Optional
from datetime import datetime, timezone
from google.cloud.firestore_v1.vector import Vector

from google.adk.tools.tool_context import ToolContext
from ...lib.embeddings import generate_embedding
from ...lib.database import get_db
from ...lib.persistence import update_document, get_local_output_dir, get_coloring_page_collection_name
from ...lib.postgres import publish_to_postgres
from ...context import get_agent_context
from ...app_configs import configs

from ...lib.version import get_agent_version

logger = logging.getLogger(__name__)

def _validate_seo_fields(
    long_description: Optional[str] = None,
    meta_description: Optional[str] = None,
    target_keyword: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Validates SEO fields:
    - long_description: 80–150 words. If invalid, logs a warning and returns None.
    - meta_description: 120–170 characters. If invalid, logs a warning and returns None.
    - target_keyword: lowercased and stripped if present.
    Never raises an exception; never blocks publish.
    """
    try:
        validated_long_desc: Optional[str] = None
        if long_description and isinstance(long_description, str) and long_description.strip():
            word_count = len(long_description.strip().split())
            if 80 <= word_count <= 150:
                validated_long_desc = long_description.strip()
            else:
                logger.warning(
                    f"[VALIDATION WARNING] 'long_description' has {word_count} words (expected 80–150). Writing NULL to Postgres."
                )

        validated_meta_desc: Optional[str] = None
        if meta_description and isinstance(meta_description, str) and meta_description.strip():
            char_count = len(meta_description.strip())
            if 120 <= char_count <= 170:
                validated_meta_desc = meta_description.strip()
            else:
                logger.warning(
                    f"[VALIDATION WARNING] 'meta_description' has {char_count} characters (expected 120–170). Writing NULL to Postgres."
                )

        validated_target_keyword: Optional[str] = None
        if target_keyword and isinstance(target_keyword, str) and target_keyword.strip():
            validated_target_keyword = target_keyword.strip().lower()

        return validated_long_desc, validated_meta_desc, validated_target_keyword
    except Exception as e:
        logger.warning(f"[VALIDATION WARNING] Error validating SEO fields: {e}. Writing NULL to Postgres.")
        return None, None, None

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
    target_keyword: Optional[str] = None,
    long_description: Optional[str] = None,
    meta_description: Optional[str] = None,
    tool_context: Optional[ToolContext] = None
) -> str:
    """
    Saves the approved coloring page metadata to Firestore and Postgres (or local file if no_persist).
    """
    ctx = get_agent_context()
    
    doc_id = ctx.document_id
    collection_name = ctx.collection_name
    no_persist = ctx.no_persist
    agent_version = ctx.agent_version

    published_date = datetime.now(timezone.utc)

    resolved_micro_style_desc = micro_style_description or (ctx.micro_style_description if ctx else None)

    user_email = ctx.user_email if ctx else None
    user_id = ctx.user_id if ctx else None
    is_user_gen = bool(user_id is not None or (ctx and ctx.is_user))

    target_col = get_coloring_page_collection_name(is_user=is_user_gen)

    # Resolve SEO fields: prefer Creative Director's saved context values; use Critic's tool args only as fallback when context is missing/empty
    ctx_long = ctx.long_description.strip() if ctx and getattr(ctx, "long_description", None) and isinstance(ctx.long_description, str) and ctx.long_description.strip() else None
    arg_long = long_description.strip() if long_description and isinstance(long_description, str) and long_description.strip() else None
    raw_long_desc = ctx_long or arg_long

    ctx_meta = ctx.meta_description.strip() if ctx and getattr(ctx, "meta_description", None) and isinstance(ctx.meta_description, str) and ctx.meta_description.strip() else None
    arg_meta = meta_description.strip() if meta_description and isinstance(meta_description, str) and meta_description.strip() else None
    raw_meta_desc = ctx_meta or arg_meta

    ctx_kw = ctx.target_keyword.strip() if ctx and getattr(ctx, "target_keyword", None) and isinstance(ctx.target_keyword, str) and ctx.target_keyword.strip() else None
    arg_kw = target_keyword.strip() if target_keyword and isinstance(target_keyword, str) and target_keyword.strip() else None
    raw_target_keyword = ctx_kw or arg_kw

    validated_long_desc, validated_meta_desc, validated_target_keyword = _validate_seo_fields(
        raw_long_desc, raw_meta_desc, raw_target_keyword
    )

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
        "user_email": user_email,
        "user_id": user_id,
        "target_keyword": validated_target_keyword,
        "long_description": validated_long_desc,
        "meta_description": validated_meta_desc,
        "agent_version": agent_version,
        "model_name": os.environ.get("MEDIA_MODEL"),
        "prompt_model_name": os.environ.get("LLM_MODEL"),
        "published_date": published_date.isoformat()
    }

    if no_persist:
        update_document(doc_id, metadata_payload, no_persist=True)
        logger.info(f"[NO_PERSIST] Published document metadata locally for ID {doc_id} (user_id={user_id})")
        if tool_context:
            tool_context.actions.escalate = True
        return f"SUCCESS: Saved '{title}' locally to review (no_persist=True) with ID {doc_id}"

    # Publish to Postgres directly for all generations (system & user)
    postgres_id = None
    full_path_gs = optimized_image_path.replace(".png", ".webp")
    thumbnail_path_gs = optimized_image_path.replace(".png", ".webp").replace("/optimized/", "/optimized/thumbnail/")

    full_path = full_path_gs.replace("gs://", "https://storage.googleapis.com/") if full_path_gs.startswith("gs://") else full_path_gs
    thumbnail_path = thumbnail_path_gs.replace("gs://", "https://storage.googleapis.com/") if thumbnail_path_gs.startswith("gs://") else thumbnail_path_gs

    page_data = {
        "name": title,
        "prompt": description,
        "tags": visual_tags,
        "generated_on": published_date,
        "width": 2550,
        "height": 3300,
        "prompt_model_name": os.environ.get("LLM_MODEL"),
        "model_name": os.environ.get("MEDIA_MODEL"),
        "generate_script": agent_version,
        "colored_path": getattr(ctx, "colored_image_path", None) if ctx else None,
        "full_path": full_path,
        "thumbnail_path": thumbnail_path,
        "reasoning": reasoning,
        "collection_unique_name": collection_name,
        "target_audience": target_audience,
        "micro_style": micro_style or (ctx.micro_style_name if ctx else None),
        "user_email": user_email,
        "user_id": user_id,
        "user": is_user_gen,
        "document_id": doc_id,
        "long_description": validated_long_desc,
        "meta_description": validated_meta_desc,
        "target_keyword": validated_target_keyword,
    }

    postgres_id = publish_to_postgres(page_data)
    if postgres_id is not None:
        metadata_payload["published"] = True
        metadata_payload["postgres_id"] = postgres_id


    db = get_db()
    batch = db.batch()
    new_doc_ref = db.collection(target_col).document(doc_id)

    # Generate Embedding for semantic search (only for admin/system pages, not user-generated)
    if not (ctx and ctx.is_user):
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
    else:
        logger.info(f"⚡ [USER REQUEST] Skipping EMBEDDING_COLLECTION write for doc '{doc_id}'")

    batch.set(new_doc_ref, metadata_payload, merge=True)
    batch.commit()

    if tool_context:
        tool_context.actions.escalate = True

    pg_msg = f" and Postgres (ID {postgres_id})" if postgres_id else ""
    return f"SUCCESS: Published '{title}' to Firestore collection '{target_col}' with ID {doc_id}{pg_msg}"


