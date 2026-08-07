import json
import logging
from typing import Optional, Dict, Any

from google import genai
from google.genai import types

from color_it_daily_agent.app_configs import configs
from color_it_daily_agent.context import get_agent_context, DEFAULT_TARGET_AUDIENCE
from color_it_daily_agent.critic.tools.download import download_image

logger = logging.getLogger(__name__)


def inspect_image_visually(
    image_path: str,
    concept_description: Optional[str] = None,
    target_audience: Optional[str] = None,
    micro_style: Optional[str] = None,
) -> str:
    """
    Visually inspects a coloring page image using Gemini Multimodal Vision API.

    Args:
        image_path (str): The GCS path (gs://...) or local file path to the image.
        concept_description (str, optional): The prompt/concept description to verify visual subject alignment.
        target_audience (str, optional): Target audience tier ('toddler', 'kids_3_10', 'tweens_teens', 'young_adults', 'adults').
        micro_style (str, optional): Chosen micro-style name or identifier to verify style compliance against.

    Returns:
        str: JSON string containing detailed visual analysis across Safety, Text, Borders, Quality, Style, Complexity, Prompt Alignment, and Anatomy.
    """
    if not isinstance(concept_description, str):
        concept_description = None
    if not isinstance(target_audience, str):
        target_audience = None
    if not isinstance(micro_style, str):
        micro_style = None

    logger.info(f"🧐 [VISUAL INSPECTION] Inspecting image: {image_path}")

    # 1. Ensure image is available locally
    local_path = download_image(gcs_path=image_path)

    with open(local_path, "rb") as f:
        image_bytes = f.read()

    # 2. Resolve context fallbacks
    ctx = get_agent_context()
    if not target_audience and ctx and ctx.target_audience:
        target_audience = ctx.target_audience
    if not target_audience:
        target_audience = DEFAULT_TARGET_AUDIENCE

    micro_style_name = micro_style or (ctx.micro_style_name if ctx else None) or (ctx.micro_style if ctx else None)
    micro_style_desc = (ctx.micro_style_description if ctx else None)

    micro_style_check = ""
    if micro_style_name and micro_style_desc:
        micro_style_check = (
            f"\n   - Target Micro-Style Name: \"{micro_style_name}\".\n"
            f"   - Target Micro-Style Requirements: \"{micro_style_desc}\".\n"
            f"   - Verify the artwork visually matches this micro-style description. For instance, if 'The Bold Sticker / Hero Subject' is requested, verify there is ZERO heavy background scenery (trees, mountains, clouds, ocean waves, rooms) and the subject is cleanly isolated on whitespace."
        )

    style_prompt_section = (
        f"5. **Micro-Style Compliance (CRITICAL):**{micro_style_check}\n"
        f"   - Does the visual artwork strictly adhere to the requested micro-style technique?"
    )

    if concept_description and concept_description.strip():
        alignment_prompt_section = (
            f"7. **Subject & Prompt Alignment (CRITICAL):**\n"
            f"   - Target Concept / Prompt Description: \"{concept_description.strip()}\".\n"
            f"   - Does the visual illustration accurately portray the main character, core action, and key visual elements described in this concept?\n"
            f"   - If the main subject or action is missing, misidentified, or incorrect, set `matches_prompt: false` and describe what is wrong."
        )
    else:
        alignment_prompt_section = (
            "7. **Subject & Prompt Alignment:** No specific concept description provided for comparison."
        )

    if target_audience == "toddler":
        complexity_section = (
            "6. **Complexity & Colorability Check (TARGET AUDIENCE: TODDLERS 1-3):**\n"
            "   - Are the outlines extra-bold and shapes extra-large with massive open coloring areas suitable for early learners?\n"
            "   - Is the page simple, clean, and completely free of tiny details or complex background noise?"
        )
    elif target_audience in ("tweens_teens", "young_adults"):
        complexity_section = (
            f"6. **Complexity & Colorability Check (TARGET AUDIENCE: {target_audience.upper()}):**\n"
            "   - Does the illustration feature clean vector outlines with moderate scene detail, balanced framing, and engaging visual structure?"
        )
    elif target_audience == "adults":
        complexity_section = (
            "6. **Complexity & Colorability Check (TARGET AUDIENCE: ADULTS 25+):**\n"
            "   - Does the illustration feature rich, detailed linework, intricate background elements, or satisfying detailed patterns ideal for adult coloring and mindfulness?"
        )
    else:
        complexity_section = (
            "6. **Complexity & Colorability Check (TARGET AUDIENCE: KIDS 3-10):**\n"
            "   - Are the shapes and colorable areas large, clear, and distinct enough for children ages 3-10 to color comfortably?\n"
            "   - Is the page free of micro-clutter, tiny uncolorable noise gaps, dense cross-hatching, or overcrowded background clutter?"
        )

    # 3. Call Gemini Multimodal Vision API
    client = genai.Client(
        vertexai=True,
        project=configs.gcp_project,
        location=configs.gcp_location,
    )

    vision_prompt = f"""
You are a strict Multimodal Vision QA inspector for children's and adult coloring pages.
Analyze the attached image pixel-by-pixel and evaluate it against these criteria:

1. **Borders & Frames (CRITICAL):**
   - Is there ANY bounding box, rectangular border line, drawn frame enclosing the illustration, dark padding, or paper edge?
   - The canvas background MUST be 100% pure white right up to the canvas edge with absolutely no border line or frame surrounding it.

2. **Text & Typography (CRITICAL):**
   - Are there ANY written words, letters, numbers, signs, titles, watermarks, logos, or signatures anywhere in the illustration?

3. **Safety & Suitability (CRITICAL - ALL AGES):**
   - Is the content 100% appropriate and safe for all audiences? (No scary elements, monsters, weapons, hate, suggestive content, or ambiguous themes).

4. **Line Quality & Shading:**
   - Are lines clean, vector-like, and unbroken?
   - Is there ZERO grayscale shading, zero gradients, zero hatch marks, and zero filled gray textures?

{style_prompt_section}

{complexity_section}

{alignment_prompt_section}

8. **Anatomy, Posing & Scene Coherence (CRITICAL):**
   - **Anatomy & Proportions**: Are character proportions, limb placements, and facial features natural and logical? Check carefully for AI image generation artifacts (extra/missing limbs, extra/fused claws, distorted faces/eyes, floating body parts).
   - **Spatial Posing & Grounding**: Does spatial positioning make sense? (e.g. character sitting/standing properly on ground/seat rather than clipping unnaturally or floating awkwardly).
   - **Scene & Element Coherence**: Do all visual elements in the illustration make logical sense together in the scene? Check that background objects, props, and environment elements are coherent (no random floating lines, nonsensical phantom objects, or chaotic disconnected shapes).
   - If anatomical defects, bad posing, or visual incoherencies exist, set `has_good_anatomy_and_coherence: false` and describe the defect in `coherence_details`.

Output **ONLY** a valid JSON object matching this schema:
{{
  "has_border_or_frame": boolean,
  "border_details": "string",
  "has_text_or_letters": boolean,
  "text_details": "string",
  "is_child_safe": boolean,
  "has_shading_or_gradients": boolean,
  "matches_micro_style": boolean,
  "is_comfortable_to_color": boolean,
  "matches_prompt": boolean,
  "prompt_alignment_details": "string",
  "has_good_anatomy_and_coherence": boolean,
  "coherence_details": "string",
  "complexity_details": "string",
  "overall_visual_pass": boolean,
  "rejection_reasons": ["string"]
}}
"""

    try:
        response = client.models.generate_content(
            model=configs.llm_model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                vision_prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        vision_result: Dict[str, Any] = json.loads(response.text)
    except Exception as e:
        logger.error(f"❌ Multimodal vision inspection failed: {e}")
        vision_result = {
            "has_border_or_frame": False,
            "border_details": "",
            "has_text_or_letters": False,
            "text_details": "",
            "is_child_safe": True,
            "has_shading_or_gradients": False,
            "matches_micro_style": True,
            "is_comfortable_to_color": True,
            "matches_prompt": True,
            "prompt_alignment_details": "",
            "has_good_anatomy_and_coherence": True,
            "coherence_details": "",
            "complexity_details": "",
            "overall_visual_pass": False,
            "rejection_reasons": [f"Vision API error: {e}"],
        }

    result_json = json.dumps(vision_result, indent=2)
    logger.info(f"🧐 [VISUAL INSPECTION RESULT]\n{result_json}")
    return result_json
