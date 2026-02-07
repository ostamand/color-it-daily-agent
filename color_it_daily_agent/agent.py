import json
import asyncio
from google.adk.agents import SequentialAgent, LoopAgent
from google.adk.runners import InMemoryRunner

from .app_configs import configs
from .creative_director.agent import creative_director
from .stylist.agent import stylist
from .generator.agent import generator
from .critic.agent import critic

# --- Orchestration ---

# The Production Chain (One iteration of the Studio Loop)
# Stylist -> Generator (which also optimizes) -> Critic
production_chain = SequentialAgent(
    name="ProductionChain", sub_agents=[stylist, generator, critic]
)

# The Studio Loop (Production Team)
# Iterates the production chain until quality standards are met (Critic passes).
# Max iterations set to 3 to prevent infinite loops and cost overrun.
studio_loop = LoopAgent(
    name="StudioLoop", sub_agents=[production_chain], max_iterations=2
)

# The Publisher (Top-Level Orchestrator)
# Manages the flow from Ideation (Creative Director) to Production (Studio Loop).
publisher = SequentialAgent(
    name="Publisher", sub_agents=[creative_director, studio_loop]
)

root_agent = publisher


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


# python -m  color_it_daily_agent.agent
if __name__ == "__main__":
    asyncio.run(main())
