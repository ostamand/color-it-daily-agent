import json
import asyncio
from google.adk.agents import LlmAgent, SequentialAgent, LoopAgent
from google.adk.models import Gemini
from google.adk.runners import InMemoryRunner

from .app_configs import configs
from .creative_director.agent import creative_director
from .stylist.instructions import INSTRUCTIONS_V1 as STYLIST_INSTRUCTIONS

# --- Sub-Agents ---

# 1. The Stylist (Sub-Agent C1)
stylist = LlmAgent(
    name="Stylist",
    instruction=STYLIST_INSTRUCTIONS,
    model=Gemini(model=configs.llm_model),
)

# --- Tools for Generator & Optimizer ---
def generate_image(positive_prompt: str, negative_prompt: str) -> str:
    """Placeholder for Nano Banana Pro API call."""
    # In a real implementation, this would call the API.
    return "/tmp/placeholder_generated_image.png"

def optimize_image(image_path: str) -> str:
    """Placeholder for Real-ESRGAN upscaling."""
    # In a real implementation, this would process the image.
    return "/tmp/placeholder_optimized_image.png"

# 2. The Generator (Tool Wrapper)
GENERATOR_INSTRUCTIONS = """
You are the Image Generator.
Your input is a JSON object containing `positive_prompt` and `negative_prompt`.
Your task is to call the `generate_image` tool with these prompts.
Output the file path returned by the tool.
"""

generator = LlmAgent(
    name="Generator",
    instruction=GENERATOR_INSTRUCTIONS,
    model=Gemini(model=configs.llm_model),
    tools=[generate_image]
)

# 3. The Optimizer (Tool Wrapper)
OPTIMIZER_INSTRUCTIONS = """
You are the Image Optimizer.
Your input is a file path to a generated image.
Your task is to call the `optimize_image` tool with this path.
Output the new file path returned by the tool.
"""

optimizer = LlmAgent(
    name="Optimizer",
    instruction=OPTIMIZER_INSTRUCTIONS,
    model=Gemini(model=configs.llm_model),
    tools=[optimize_image]
)

# 4. The Critic (Sub-Agent C2)
# TODO: Move instructions to a dedicated file (e.g., color_it_daily_agent/critic/instructions.py)
CRITIC_INSTRUCTIONS = """
You are a strict art critic for children's coloring pages.
1. **Safety Check (Zero Tolerance):** Reject if content is scary, suggestive, or ambiguous.
2. **Quality Check:** Reject if lines are broken/faint or image contains grayscale shading.
3. **Composition Check:**
    * If 'Sticker': Reject if background is cluttered.
    * If 'Collection': Reject if items overlap or touch.
4. **Complexity Check:** Reject if details are too small for crayons.

Output: `Status` (PASS/REJECT), `Feedback`.
"""

critic = LlmAgent(
    name="Critic",
    instruction=CRITIC_INSTRUCTIONS,
    model=Gemini(model=configs.llm_model),
)

# --- Orchestration ---

# The Production Chain (One iteration of the Studio Loop)
production_chain = SequentialAgent(
    name="ProductionChain",
    agents=[stylist, generator, optimizer, critic]
)

# The Studio Loop (Production Team)
# Iterates the production chain until quality standards are met (Critic passes).
studio_loop = LoopAgent(
    name="StudioLoop",
    agent=production_chain,
    # TODO: Implement loop condition (e.g., stopping when Critic returns PASS)
    # max_iterations=3 
)

# The Publisher (Top-Level Orchestrator)
# Manages the flow from Ideation (Creative Director) to Production (Studio Loop).
publisher = SequentialAgent(
    name="Publisher",
    agents=[creative_director, studio_loop]
)

async def main():
    from datetime import datetime
    now = datetime.now()
    current_date_str = now.strftime("%Y-%m-%d")

    runner = InMemoryRunner(agent=publisher)

    print(f"Starting Publisher Agent for {current_date_str}...")
    
    # Example user request payload
    user_request = {
        "current_date": current_date_str,
    }

    await runner.run_debug(
        json.dumps(user_request), 
        verbose=True,
    )

if __name__ == "__main__":
    asyncio.run(main())
