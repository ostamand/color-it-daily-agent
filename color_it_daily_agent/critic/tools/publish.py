import os
from typing import List
from datetime import datetime
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector

from ...lib.embeddings import generate_embedding
from ...lib.database import get_db
from ...app_configs import configs

def publish_to_firestore(
    title: str,
    description: str,
    visual_tags: List[str],
    mood: str,
    target_audience: str,
    positive_prompt: str,
    negative_prompt: str,
    optimized_image_path: str,
    status: str,
    feedback: str
) -> str:
    """
    Saves the approved coloring page metadata to Firestore.
    
    Args:
        title (str): The title of the coloring page.
        description (str): The visual description.
        visual_tags (List[str]): List of tags.
        mood (str): The emotional tone.
        target_audience (str): The target audience.
        positive_prompt (str): The positive prompt used.
        negative_prompt (str): The negative prompt used.
        optimized_image_path (str): The GCS path to the final asset.
        status (str): The final status (e.g. "PASS").
        feedback (str): The critic's feedback.
        
    Returns:
        str: A success message with the document ID.
    """
    db = get_db()
    
    # 1. Prepare Data
    published_date = datetime.now()
    
    # 2. Extract ID from optimized_image_path (the uuid generated during production)
    # Example: gs://bucket/optimized/abc-123.png -> abc-123
    filename = os.path.basename(optimized_image_path)
    doc_id = os.path.splitext(filename)[0]
    
    # Generate Embedding for semantic search
    embedding_vector = generate_embedding(description, task_type="RETRIEVAL_DOCUMENT")
    
    # 3. Transactional Write (Recommended) or Batch
    # We want to ensure both the metadata and the vector are saved.
    batch = db.batch()
    
    # Create document ref using the extracted ID
    new_doc_ref = db.collection(configs.coloring_page_collection).document(doc_id)
    
    # Data for the main collection (Metadata)
    metadata_payload = {
        "published": False,
        "title": title,
        "description": description,
        "visual_tags": visual_tags,
        "mood": mood,
        "target_audience": target_audience,
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "optimized_image_path": optimized_image_path,
        "status": status,
        "feedback": feedback,
        "published_date": published_date,
        # Flatten tags for easier basic filtering if needed
        "tags_search": visual_tags
    }
    
    # Data for the vector collection (Similarity Search)
    # We use the SAME document ID so we can easily join them later
    vector_ref = db.collection(configs.embedding_collection).document(doc_id)
    vector_payload = {
        "embedding": Vector(embedding_vector),
        "published_date": published_date # duplicate for sorting if needed
    }
    
    # Queue operations
    batch.set(new_doc_ref, metadata_payload)
    batch.set(vector_ref, vector_payload)
    
    # Commit
    batch.commit()
    
    return f"SUCCESS: Published '{title}' to Firestore with ID {doc_id}"
