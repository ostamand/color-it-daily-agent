import os
from google import genai
from google.genai.types import EmbedContentConfig

from color_it_daily_agent.lib.retry_utils import retry_genai_call

_client = None


def get_genai_client():
    global _client
    if _client is None:
        _client = genai.Client()
    return _client


@retry_genai_call
def _call_embed_content(client, model, contents, config):
    return client.models.embed_content(
        model=model,
        contents=contents,
        config=config,
    )


def generate_embedding(
    text: str,
    task_type: str = "RETRIEVAL_QUERY",
    model: str = "text-embedding-004",
    dimensionality: int = 768,
) -> list[float]:
    """
    Generates a text embedding using the Google Gen AI SDK.

    Args:
        text (str): The content to embed.
        task_type (str):
            'RETRIEVAL_QUERY' - For searching (e.g., inside the Agent tool).
            'RETRIEVAL_DOCUMENT' - For indexing (e.g., when saving to Firestore).
        model (str): The embedding model ID. Defaults to 'text-embedding-004'.
        dimensionality (int): Size of the vector. 768 is standard for this model.
                              (Using lower dimensionality saves database costs).

    Returns:
        list[float]: The embedding vector values.
    """
    client = get_genai_client()

    try:
        response = _call_embed_content(
            client,
            model=model,
            contents=[text],
            config=EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=dimensionality,
                title=(
                    "Coloring Page Concept"
                    if task_type == "RETRIEVAL_DOCUMENT"
                    else None
                ),
            ),
        )

        return response.embeddings[0].values

    except Exception as e:
        print(f"Error generating embedding: {e}")
        return []
