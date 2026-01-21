from typing import List

from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud import firestore

from ...lib.embeddings import generate_embedding
from ...lib.database import get_db
from ...app_configs import configs

def get_recent_history(limit: int = 3) -> List[str]:
    """
    Retrieves the titles and visual tags of the most recently published coloring pages from Firestore.
    Used to check what categories we have just done (e.g., 'Space' or 'Dinosaurs')
    so the Creative Director can choose a DIFFERENT category for today.

    Args:
        limit (int): How many past days to look back. Defaults to 3.

    Returns:
        List[str]: A summary of recent pages, e.g.,
                   ["Title: Space Cat | Tags: space, animal", "Title: Firetruck | Tags: vehicle"]
    """

    # 1. Query Firestore: Collection 'coloring_pages' -> Order by Date DESC -> Limit
    db = get_db()
    docs = (
        db.collection(configs.coloring_page_collection)
        .order_by("published_date", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )

    summary = []

    # 2. Format results for the LLM
    for doc in docs:
        data = doc.to_dict()
        title = data.get("title", "Untitled")

        # Handle tags safely (they might be stored as a list or missing)
        tags = data.get("visual_tags", [])
        if isinstance(tags, list):
            tags_str = ", ".join(tags)
        else:
            tags_str = str(tags)

        summary.append(f"Title: {title} | Tags: {tags_str}")

    # 3. Handle empty state (First run ever)
    if not summary:
        return ["No history found. You are free to pick any category."]

    return summary


def search_past_concepts(concept_description: str) -> list[dict]:
    """
    Searches for similar past concepts using a separate vector collection.

    1. Generates embedding for the input description.
    2. Searches `coloring_pages_vectors` for similarity.
    3. Uses the resulting IDs to fetch metadata from `coloring_pages`.

    Args:
        concept_description (str): The visual description of the new idea.

    Returns:
        list[dict]: A list of similar past pages (Title, Tags, etc.).
    """
    db = get_db()

    # 1. Generate Embedding (You need your embedding function here)
    # This is a placeholder. in reality: embedding = model.embed(concept_description)
    # For now, we assume you have a helper function 'generate_embedding'
    query_embedding = generate_embedding(
        concept_description, task_type="RETRIEVAL_QUERY"
    )

    # 2. Step 1: Vector Search on the 'vectors' collection
    vector_coll = db.collection(configs.embedding_collection)

    vector_results = vector_coll.find_nearest(
        vector_field="embedding",
        query_vector=Vector(query_embedding),
        distance_measure=DistanceMeasure.COSINE,
        limit=5,
    ).get()

    if not vector_results:
        return []

    # 3. Step 2: efficient Batch Fetch from the 'main' collection
    # We assume the document IDs are identical in both collections.
    doc_ids = [doc.id for doc in vector_results]

    # Create references to the main content documents
    content_refs = [
        db.collection(configs.coloring_page_collection).document(doc_id) for doc_id in doc_ids
    ]

    # Fetch all metadata in one network request
    content_docs = db.get_all(content_refs)

    results = []
    for doc in content_docs:
        if doc.exists:
            data = doc.to_dict()
            results.append(
                {
                    "title": data.get("title"),
                    "visual_tags": data.get("visual_tags"),
                    # We don't need to return the vector or the ID to the LLM
                }
            )

    return results
