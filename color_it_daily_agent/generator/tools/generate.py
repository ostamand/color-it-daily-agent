import os
import uuid
import base64
import logging
from typing import Optional

from google import genai
from google.genai import types
from google.cloud import storage

from color_it_daily_agent.app_configs import configs
from color_it_daily_agent.context import get_agent_context
from color_it_daily_agent.lib.persistence import get_local_output_dir

logger = logging.getLogger(__name__)

def generate_image(positive_prompt: str, negative_prompt: Optional[str] = None) -> str:
    """
    Generates an image using the configured media model and uploads it to GCS (or saves locally if no_persist).
    
    Args:
        positive_prompt (str): The detailed description of what to generate.
        negative_prompt (str, optional): Deprecated / unused.

    Returns:
        str: The GCS path (or local file path if no_persist) of the raw generated image.
    """
    ctx = get_agent_context()
    generation_id = ctx.document_id if ctx else str(uuid.uuid4())

    ai_client = genai.Client(
        vertexai=True,
        project=configs.gcp_project,
        location=configs.gcp_location,
    )

    full_prompt_text = positive_prompt
    logger.info(f"\n==================== [GENERATING IMAGE PROMPT] ====================\n{positive_prompt}\n===================================================================")
    prompt_part = types.Part.from_text(text=full_prompt_text)

    contents = [
        types.Content(role="user", parts=[prompt_part]),
    ]


    generate_content_config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        safety_settings=[
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_LOW_AND_ABOVE"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_LOW_AND_ABOVE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="BLOCK_LOW_AND_ABOVE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_LOW_AND_ABOVE"
            ),
        ],
        image_config=types.ImageConfig(
            aspect_ratio="3:4",
            image_size="1K",
            output_mime_type="image/png",
        ),
    )

    try:
        response = ai_client.models.generate_content(
            model=configs.media_model,
            contents=contents,
            config=generate_content_config,
        )

        image_data = None
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_data = part.inline_data.data
                    break

        if not image_data:
            raise ValueError("No image data found in response.")

        if isinstance(image_data, str):
            image_bytes = base64.b64decode(image_data)
        else:
            image_bytes = image_data

        if ctx and ctx.no_persist:
            local_dir = get_local_output_dir(generation_id)
            raw_path = os.path.join(local_dir, "raw.png")
            with open(raw_path, "wb") as f:
                f.write(image_bytes)
            logger.info(f"[NO_PERSIST] Raw image saved locally to '{raw_path}'")
            return raw_path

        storage_client = storage.Client(project=configs.gcp_project)
        filename = f"raw/{generation_id}.png"
        bucket = storage_client.bucket(configs.gcp_media_bucket)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type="image/png")

        return f"gs://{configs.gcp_media_bucket}/{filename}"

    except Exception as e:
        logger.error(f"❌ Image generation failed: {e}")
        raise e


if __name__ == "__main__":
    # Test the tool
    test_positive = "A pristine, black-and-white coloring page designed for children. A happy penguin is gliding gracefully across the surface of a smooth, frozen pond. The penguin is wearing a simple striped scarf and small ice skates. The background is a peaceful winter scene featuring a few rounded, snow-covered pine trees and a small, gentle snowy hill. The line work is fluid, friendly, and organic, using thick, uniform black lines on a pure white background. The composition is uncluttered with large, closed shapes and absolutely no shading, textures, or grayscale fills."
    test_negative = "sharp ice cracked ice, thin lines, complex textures, shading, grayscale, gradients, photographic realism, messy sketches, small intricate details, dark backgrounds, cross-hatching"
    
    try:
        print(f"Generating image for: {test_positive}")
        result_path = generate_image(test_positive, test_negative)
        print(f"✅ Generated image saved to: {result_path}")
    except Exception as e:
        print(f"❌ Test failed: {e}")
