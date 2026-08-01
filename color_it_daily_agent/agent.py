import json
import asyncio
from google.adk.agents import SequentialAgent, LoopAgent
from google.adk.runners import InMemoryRunner
from datetime import datetime

from .app_configs import configs
from .creative_director.agent import creative_director
from .stylist.agent import stylist
from .generator.agent import generator
from .critic.agent import critic
from .lib.trace_plugin import PromptTracePlugin

# --- Orchestration ---

# Stylist -> Generator (which also optimizes) -> Critic
production_chain = SequentialAgent(
    name="ProductionChain", sub_agents=[stylist, generator, critic]
)

# Iterates the production chain until quality standards are met (Critic passes).
# Max iterations set to 3 to prevent infinite loops and cost overrun.
studio_loop = LoopAgent(
    name="StudioLoop", sub_agents=[production_chain], max_iterations=2
)

# Manages the flow from Ideation (Creative Director) to Production (Studio Loop).
publisher = SequentialAgent(
    name="Publisher", sub_agents=[creative_director, studio_loop]
)

root_agent = publisher


async def main():
    now = datetime.now()
    current_date_str = now.strftime("%Y-%m-%d")

    runner = InMemoryRunner(agent=publisher, plugins=[PromptTracePlugin()])

    print(f"Starting Publisher Agent for {current_date_str}...")

    user_request = {
        "current_date": current_date_str,
    }

    await runner.run_debug(
        json.dumps(user_request),
        verbose=True,
    )


# python -m  color_it_daily_agent.agent
if __name__ == "__main__":
    asyncio.run(main())
