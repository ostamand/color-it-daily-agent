import contextvars
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class AgentContext:
    document_id: str
    current_date: str
    collection_name: str = "Wonder Daily"
    no_persist: bool = False
    target_keyword: Optional[str] = None
    collection_context: Optional[str] = None
    collection_description: Optional[str] = None
    creative_skill: str = "Thick Line Art – Bold, clean outlines with no shading or fills. Pure black-and-white coloring book style suitable for children ages 3-10."
    collection_data: Dict[str, Any] = field(default_factory=dict)
    local_output_dir: str = ""

_context_var: contextvars.ContextVar[Optional[AgentContext]] = contextvars.ContextVar("agent_context", default=None)

def set_agent_context(ctx: AgentContext) -> None:
    _context_var.set(ctx)

def get_agent_context() -> Optional[AgentContext]:
    return _context_var.get()
