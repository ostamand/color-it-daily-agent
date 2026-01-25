import json
import asyncio

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.runners import InMemoryRunner

from .instructions import INSTRUCTIONS_V1
from .tools.calendar import get_calendar_events
from .tools.history import get_recent_history, search_past_concepts
from ..app_configs import configs

creative_director = LlmAgent(
    name="CreativeDirector",
    instruction=INSTRUCTIONS_V1,
    model=Gemini(model=configs.llm_model),  
    tools=[get_calendar_events, get_recent_history, search_past_concepts],
)

async def main():
    from datetime import datetime
    now = datetime.now()
    current_date_str = now.strftime("%Y-%m-%d")

    runner = InMemoryRunner(agent=creative_director)

    user_request = {
        "current_date": current_date_str,
    }

    await runner.run_debug(
        json.dumps(user_request),
        verbose=True,
    )

# python -m  color_it_daily_agent.creative_director.agent
if __name__ == "__main__":
    asyncio.run(main())
