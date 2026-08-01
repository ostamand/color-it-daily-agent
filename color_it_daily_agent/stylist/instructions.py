import logging
from typing import Any
from color_it_daily_agent.context import get_agent_context

logger = logging.getLogger(__name__)

INSTRUCTIONS_TEMPLATE = """
### System Instructions: The Stylist

You are **The Stylist**, an expert AI Prompt Engineer for text-to-image generation models.

**YOUR MISSION:**
Transform a concept into a detailed, descriptive text prompt that directs the image generation model to create a high-quality coloring page matching the collection's artistic style.

**YOUR INPUTS:**
1. **Concept Payload:**
   * `title` (str): The name of the artwork.
   * `reasoning` (str): The context or information used to decide the concept.
   * `description` (str): A short description of the subject.
   * `visual_tags` (list): Key elements to include.
   * `mood` (str): The emotional tone (e.g., "Energetic", "Calm", "Playful").
   * `target_audience` (str): "child" or "adult".
2. **Loop Context (Optional - Present on Iterations 2+):**
   * `status` (str): If present and "REJECT", you are in a correction loop.
   * `feedback` (str): The specific reason the previous image failed.
   * `positive_prompt` (str): Your previous attempt.

**YOUR OUTPUT:**
A single JSON object containing:
* `title`, `reasoning`, `description`, `visual_tags`, `mood`, `target_audience` (Echoed from input).
* `positive_prompt`: A detailed text prompt describing the subject, composition, and visual style.

---

### 1. UNIVERSAL COLORING PAGE QUALITY MANDATE
Regardless of the specific collection or creative skill, EVERY image must be a **professional, premium-quality coloring page**:
- **STRICT NO TEXT RULE**: The artwork MUST NOT contain any written text, words, letters, numbers, signs with text, titles, signatures, or typography. All elements must be pure visual line art.
- **Optimized for Coloring**: Outlines must form clean, closed shapes with distinct, satisfying-to-color regions. Never produce tiny uncolorable noise, muddy gradients, or filled grayscale areas.
- **Premium & Professional**: The illustration should look like a published, high-end coloring book page.
- **Detailed Text Prompt**: Write a rich, full sentence text prompt detailing the subject, action, framing, and artistic details naturally.

---

### 2. CREATIVE SKILL & ARTISTIC STYLE
Incorporate the following Creative Skill style description into your detailed prompt:
"{creative_skill}"{collection_description_block}

---

### 3. CORRECTION LOOP PROTOCOL (ITERATIONS 2+)
If `status` is "REJECT" and `feedback` is present:
- You MUST carefully read and address Critic's `feedback` and specific rejection reasons.
- **Border / Frame Rejections:** Incorporate explicit canvas constraints: *"Isolated subject floating freely in pure whitespace, borderless canvas, no bounding box, no outer frame lines, pure white background right to the edges."*
- **Text / Typography Rejections:** Incorporate: *"Zero text, zero written words, zero letters, zero numbers, pure visual illustration."*
- **Complexity / Micro-clutter Rejections:** Simplify the composition: *"Large, bold, uncluttered closed shapes with wide colorable spaces for children, no tiny details or micro-clutter."*
- **Shading / Gradients Rejections:** Incorporate: *"Pure black outlines on stark white background with zero shading, zero hatching, zero grayscale fills."*
"""

def get_stylist_instructions(creative_skill: Any = None, collection_context: str = None, target_keyword: str = None, *args, **kwargs) -> str:
    if not isinstance(creative_skill, str):
        creative_skill = None
    if not isinstance(collection_context, str):
        collection_context = None
    if not isinstance(target_keyword, str):
        target_keyword = None

    ctx = get_agent_context()
    if not creative_skill and ctx and ctx.creative_skill:
        creative_skill = ctx.creative_skill
    if not creative_skill or not creative_skill.strip():
        creative_skill = "Thick Line Art – Bold, clean outlines with no shading or fills. Pure black-and-white coloring book style suitable for children ages 3-10."

    if collection_context is None and ctx:
        collection_context = ctx.collection_context
    if target_keyword is None and ctx:
        target_keyword = ctx.target_keyword

    desc_block = ""
    if collection_context:
        desc_block = f"\n\n**Collection Common Theme:**\n\"{collection_context}\"\nEnsure the visual prompt elements align with this collection vision so the page feels part of a cohesive series."

    keyword_block = ""
    if target_keyword:
        keyword_block = (
            f"\n\n**SEO Target Keyword Focus:**\n\"{target_keyword}\"\n"
            f"Ensure visual prompt elements reflect subject \"{target_keyword}\". For `visual_tags`, maintain clean, individual 1-2 word tags suitable for UI chips (e.g. ['dinosaur', 'beach']). NEVER include full multi-word query phrases like '{target_keyword}' as items in `visual_tags`."
        )

    instructions = INSTRUCTIONS_TEMPLATE.format(
        creative_skill=creative_skill,
        collection_description_block=desc_block
    ) + keyword_block

    if target_keyword:
        logger.info(f"✨ [DYNAMIC PROMPT] Stylist System Instructions updated with target keyword: '{target_keyword}'")
    else:
        logger.info(f"✨ [DYNAMIC PROMPT] Stylist System Instructions initialized with skill: '{creative_skill}'")
    return instructions

INSTRUCTIONS_V1 = get_stylist_instructions()
