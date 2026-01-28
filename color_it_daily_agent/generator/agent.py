import json
import asyncio

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.models import Gemini
from google.adk.runners import InMemoryRunner


from .instructions import INSTRUCTIONS_V1
from .tools.generate import generate_image
from ..app_configs import configs

# Define the Generator agent
generator = LlmAgent(
    name="Generator",
    instruction=INSTRUCTIONS_V1,
    model=Gemini(model=configs.llm_model),
    tools=[generate_image],
)

# python -m  color_it_daily_agent.generator.agent
async def main():
    from datetime import datetime
    now = datetime.now()
    current_date_str = now.strftime("%Y-%m-%d")

    from ..creative_director.agent import creative_director
    from ..stylist.agent import stylist

    sequential_agent = SequentialAgent(name="SequentialAgent", sub_agents=[
        creative_director, stylist, generator
    ])

    runner = InMemoryRunner(agent=sequential_agent)

    user_request = {
        "current_date": current_date_str,
    }

    await runner.run_debug(
        json.dumps(user_request),
        verbose=True,
    )

if __name__ == "__main__":
    asyncio.run(main())
