import os
import logging
import uuid
import base64
import json
import io
import functions_framework
from google.cloud import firestore
from google.cloud import storage
from google import genai
from google.genai import types
from PIL import Image
from typing import List, Optional
from dotenv import load_dotenv
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

# Load environment variables for local development
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment Variables
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
COLORING_PAGE_COLLECTION = os.environ.get("COLORING_PAGE_COLLECTION", "coloring_pages")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "us-central1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.0-flash-exp") # Default to a capable vision model

def get_style_instruction(audience: str, mood: str, tags: List[str]) -> str:
    """
    Determines the coloring style based on metadata, mirroring the Stylist agent's logic.
    """
    audience = audience.lower() if audience else "child"
    mood = mood.lower() if mood else ""
    tags = [t.lower() for t in tags] if tags else []

    if audience == "child":
        # Micro-Style 6: Simple Mosaic (Nature/Patterns)
        if any(t in tags for t in ["butterfly", "snowflake", "leaf", "abstract"]):
            return "Style: Simple Mosaic. Color like a simple stained-glass window. Use bright, distinct colors for each segment."
        
        # Micro-Style 5: Simple Mandala (Symmetry)
        if "mandala" in tags or "symmetry" in tags or any(t in tags for t in ["flower", "snowflake"]):
             return "Style: Simple Mandala. Use a radial symmetrical color palette. Bright and engaging colors suitable for children."

        # Micro-Style 3: Kawaii Pop (Cute)
        if mood in ["fun", "happy"] or any(t in tags for t in ["cute", "baby", "sweet", "chibi"]):
            return "Style: Kawaii Pop. Use a pastel and bright color palette. Soft, cute, and happy colors."

        # Micro-Style 4: Dynamic Comic (Action)
        if mood in ["energetic", "adventure"] or any(t in tags for t in ["sports", "hero", "vehicle", "car", "train", "plane"]):
            return "Style: Dynamic Comic. Use bold, vibrant, and saturated colors. High contrast."

        # Micro-Style 2: Whimsical Storybook (Scenes)
        if mood in ["calm", "dreamy"] or any(t in tags for t in ["nature", "scenery", "forest"]):
            return "Style: Whimsical Storybook. Use soft, watercolor-like hues. Gentle, warm, and inviting colors."
        
        # Micro-Style 1: Bold Sticker (Default)
        return "Style: Bold Sticker. Use high-impact, solid colors. Make the subject pop against the background."

    else: # Adult
        if any(t in tags for t in ["animal", "nature", "flower"]):
            return "Style: Botanical & Organic. Use realistic, naturalistic colors with subtle gradients and blending."
        
        return "Style: Zen Mandala. Use a sophisticated, harmonious color palette. Relaxing and meditative colors."

@retry(
    retry=retry_if_exception_type(Exception), # Broad retry for API errors, specifically 429s which come as ClientError
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def generate_colored_image(ai_client, model_name, contents, config):
    """
    Calls Gemini API with retry logic.
    """
    logger.info(f"Calling Gemini Model: {model_name}")
    return ai_client.models.generate_content(
        model=model_name,
        contents=contents,
        config=config,
    )

@functions_framework.cloud_event
def colorize_image(cloud_event):
    """
    Triggered by a file change in the GCS bucket.
    """
    data = cloud_event.data
    
    bucket_name = data["bucket"]
    file_name = data["name"]
    
    # Filter: Only trigger on .webp files in /optimized/thumbnail/
    if not file_name.endswith(".webp") or "optimized/thumbnail/" not in file_name:
        logger.info(f"Skipping file: {file_name}")
        return

    logger.info(f"Processing file: gs://{bucket_name}/{file_name}")

@retry(
    retry=retry_if_exception_type(ValueError), # Retry if we raise ValueError for missing doc
    stop=stop_after_attempt(10), # Try for a bit longer (e.g. up to ~2 mins total with backoff)
    wait=wait_exponential(multiplier=1, min=2, max=15),
    before_sleep=before_sleep_log(logger, logging.INFO)
)
def fetch_firestore_document(db_client, collection_name, doc_id):
    """
    Fetches a Firestore document with retry logic if it doesn't exist yet.
    """
    doc_ref = db_client.collection(collection_name).document(doc_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise ValueError(f"Document {doc_id} not found yet.")
    
    return doc, doc_ref

@functions_framework.cloud_event
def colorize_image(cloud_event):
    """
    Triggered by a file change in the GCS bucket.
    """
    data = cloud_event.data
    
    bucket_name = data["bucket"]
    file_name = data["name"]
    
    # Filter: Only trigger on .webp files in /optimized/thumbnail/
    if not file_name.endswith(".webp") or "optimized/thumbnail/" not in file_name:
        logger.info(f"Skipping file: {file_name}")
        return

    logger.info(f"Processing file: gs://{bucket_name}/{file_name}")

    try:
        # 1. Extract ID
        # Path: optimized/thumbnail/<ID>.webp
        basename = os.path.basename(file_name)
        image_id = os.path.splitext(basename)[0]
        logger.info(f"Extracted Image ID: {image_id}")

        # 2. Fetch Metadata from Firestore (with retry)
        db_firestore = firestore.Client(project=PROJECT_ID)
        try:
            doc, doc_ref = fetch_firestore_document(db_firestore, COLORING_PAGE_COLLECTION, image_id)
        except Exception as e:
            logger.error(f"Failed to fetch metadata for {image_id} after retries: {e}")
            return # Exit if we truly can't find the metadata

        metadata = doc.to_dict()
        description = metadata.get("description", "")
        mood = metadata.get("mood", "")
        tags = metadata.get("visual_tags", [])
        audience = metadata.get("target_audience", "child")
        
        # 3. Construct Paths
        # Raw Image Path (Input for Gemini)
        raw_image_uri = f"gs://{bucket_name}/raw/{image_id}.png"
        
        # Colored Image Path (Output)
        colored_filename = f"optimized/colored/{image_id}.webp"
        colored_image_uri = f"gs://{bucket_name}/{colored_filename}"
        public_colored_url = f"https://storage.googleapis.com/{bucket_name}/{colored_filename}"

        # 4. Determine Style & Construct Prompt
        style_instruction = get_style_instruction(audience, mood, tags)
        
        prompt_text = f"""
        You are an expert professional colorist.
        
        **TASK:**
        Colorize the provided line-art image.
        
        **STRICT CONSTRAINTS:**
        1. **PRESERVE LINES:** Do NOT add, remove, or modify any lines. The original line art must remain exactly as is, simply colored in.
        2. **NO NEW ELEMENTS:** Do NOT add any new objects, background elements, or textures that are not in the line art.
        3. **STYLE:** {style_instruction}
        4. **CONTEXT:** The image depicts: {description}
        5. **OUTPUT:** Return ONLY the colored image.
        """

        logger.info(f"Prompting Gemini with: {style_instruction}")

        # 5. Call Gemini API
        ai_client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location=GCP_LOCATION,
        )

        image_part = types.Part.from_uri(file_uri=raw_image_uri, mime_type="image/png")
        text_part = types.Part.from_text(text=prompt_text)

        contents = [
            types.Content(role="user", parts=[text_part, image_part]),
        ]

        generate_content_config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        )

        # Call the retriable function
        response = generate_colored_image(ai_client, MODEL_NAME, contents, generate_content_config)

        # 6. Extract, Resize, and Upload Result
        image_data = None
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_data = part.inline_data.data
                    break
        
        if not image_data:
            raise ValueError("Gemini response did not contain an image.")

        if isinstance(image_data, str):
            image_bytes = base64.b64decode(image_data)
        else:
            image_bytes = image_data

        # Load generated image
        colored_img = Image.open(io.BytesIO(image_bytes))

        # Get trigger image size
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(bucket_name)
        trigger_blob = bucket.blob(file_name)
        trigger_bytes = trigger_blob.download_as_bytes()
        trigger_img = Image.open(io.BytesIO(trigger_bytes))
        target_size = trigger_img.size
        logger.info(f"Target size from thumbnail: {target_size}")

        # Resize to match trigger size
        if colored_img.size != target_size:
            logger.info(f"Resizing from {colored_img.size} to {target_size}")
            colored_img = colored_img.resize(target_size, Image.Resampling.LANCZOS)

        # Save to buffer as WebP
        output_buffer = io.BytesIO()
        colored_img.save(output_buffer, format="WEBP")
        output_buffer.seek(0)

        blob = bucket.blob(colored_filename)
        blob.upload_from_file(output_buffer, content_type="image/webp")
        blob.make_public()
        
        logger.info(f"Uploaded colored image to: {colored_image_uri}")

        # 7. Update Firestore with new colored path
        try:
            doc_ref.update({"colored_image_path": public_colored_url})
            logger.info(f"Updated Firestore document {image_id} with colored_image_path: {public_colored_url}")
        except Exception as e:
            logger.error(f"Firestore Update Failed: {e}")
            raise e

    except Exception as e:
        logger.error(f"Error processing {file_name}: {e}")
        # We generally don't want to retry indefinitely on fatal errors, but strict error handling is key.
        raise e
