import contextvars
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from color_it_daily_agent.lib.version import get_agent_version

VALID_TARGET_AUDIENCES = [
    "toddler",
    "kids_3_10",
    "tweens_teens",
    "young_adults",
    "adults",
]

DEFAULT_TARGET_AUDIENCE = "kids_3_10"


@dataclass
class AgentContext:
    document_id: str
    current_date: str
    collection_name: str = "Wonder Daily"
    no_persist: bool = False
    target_keyword: Optional[str] = None
    target_audience: str = DEFAULT_TARGET_AUDIENCE
    collection_context: Optional[str] = None
    collection_description: Optional[str] = None
    creative_skill: str = (
        "Thick Line Art – Bold, clean outlines with no shading or fills. "
        "Pure black-and-white coloring book style."
    )
    collection_data: Dict[str, Any] = field(default_factory=dict)
    local_output_dir: str = ""
    agent_version: str = field(default_factory=get_agent_version)


_context_var: contextvars.ContextVar[Optional[AgentContext]] = (
    contextvars.ContextVar("agent_context", default=None)
)


def set_agent_context(ctx: AgentContext) -> None:
    _context_var.set(ctx)


def get_agent_context() -> Optional[AgentContext]:
    return _context_var.get()
