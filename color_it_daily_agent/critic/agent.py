import json
import asyncio

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.runners import InMemoryRunner

from .instructions import INSTRUCTIONS_V1
from .tools.download import download_image
from .tools.publish import publish_to_firestore
from ..app_configs import configs

critic = LlmAgent(
    name="Critic",
    instruction=INSTRUCTIONS_V1,
    model=Gemini(model=configs.llm_model),
    tools=[download_image, publish_to_firestore]
)

async def main():
    runner = InMemoryRunner(agent=critic)
    
    # Example input simulating a completed generation ready for critique
    test_input = {
        "title": "The Cozy Puzzle Squirrel",
        "description": "A cheerful squirrel wearing a thick, knitted sweater sits on a small stool at a wooden table. The squirrel is happily placing a large jigsaw puzzle piece into a puzzle spread across the table. In the background, a window shows a peaceful snowy day, and a steaming mug of cocoa sits nearby.",
        "visual_tags": [
            "squirrel",
            "puzzle",
            "winter",
            "scenery",
            "cozy"
        ],
        "mood": "Calm",
        "target_audience": "child",
        "positive_prompt": "A pristine, black-and-white coloring page designed for children. Illustrate a soft, whimsical storybook scene of a cheerful squirrel wearing a thick, knitted sweater sitting on a small wooden stool. The squirrel is happily holding a large, chunky jigsaw puzzle piece above a simple puzzle on a table. Next to him sits a steaming mug of cocoa. In the background, a simple window frame reveals a peaceful snowy day with a few large snowflakes. Use fluid, organic line work that feels friendly and inviting, keeping the background sparse and uncluttered. The image uses thick, uniform black lines on a pure white background with absolutely no shading, texture, or grayscale fill.",
        "negative_prompt": [
            "shading",
            "grayscale",
            "texture",
            "tiny puzzle pieces",
            "sharp edges",
            "clutter",
            "complex patterns",
            "realistic fur",
            "photorealistic",
            "dark shadows",
            "thin lines",
            "messy lines",
            "hatching"
        ],
        "raw_image_path": "gs://color-it-daily-agent-assets/raw/ccdd3d36-dbc6-40a6-8bf1-d8259e530b0d.png",
        "optimized_image_path": "gs://color-it-daily-agent-assets/optimized/ccdd3d36-dbc6-40a6-8bf1-d8259e530b0d.png"
    }

    print(f"Starting Critic Agent with test input...")
    
    await runner.run_debug(
        json.dumps(test_input),
        verbose=True,
    )

# python -m  color_it_daily_agent.critic.agent
if __name__ == "__main__":
    asyncio.run(main())
