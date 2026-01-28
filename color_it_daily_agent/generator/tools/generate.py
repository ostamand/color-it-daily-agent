import uuid
import base64
from typing import Optional

from google import genai
from google.genai import types
from google.cloud import storage

from color_it_daily_agent.app_configs import configs

def generate_image(positive_prompt: str, negative_prompt: Optional[str] = None) -> str:
    """
    Generates an image using the configured media model and uploads it to GCS.
    
    Args:
        positive_prompt (str): The description of what to generate.
        negative_prompt (str, optional): The description of what to avoid.

    Returns:
        str: The GCS path of the raw generated image (e.g., gs://bucket/raw/uuid.png).
    """
    # Generate a unique ID for this generation
    generation_id = str(uuid.uuid4())

    ai_client = genai.Client(
        vertexai=True,
        project=configs.gcp_project,
        location=configs.gcp_location,
    )

    storage_client = storage.Client(project=configs.gcp_project)

    # Combine prompts if negative prompt is provided.
    # The 'gemini-2.5-flash-image' model uses the generate_content API, 
    # where negative prompts are typically handled via the text prompt instructions.
    full_prompt_text = positive_prompt
    if negative_prompt:
        full_prompt_text = f"{positive_prompt}\n\nNegative prompt: {negative_prompt}"

    prompt_part = types.Part.from_text(text=full_prompt_text)

    contents = [
        types.Content(role="user", parts=[prompt_part]),
    ]

    # Configuration for image generation
    # ImageConfig for generate_content does not support 'negative_prompt' directly.
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

        filename = f"raw/{generation_id}.png"
        bucket = storage_client.bucket(configs.gcp_media_bucket)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type="image/png")

        return f"gs://{configs.gcp_media_bucket}/{filename}"

    except Exception as e:
        print(f"❌ Image generation failed: {e}")
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
