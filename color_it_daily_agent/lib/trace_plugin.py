import os
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from google.adk.plugins.base_plugin import BasePlugin
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.base_tool import BaseTool
from google.adk.models import LlmRequest, LlmResponse
from google.cloud import firestore

from color_it_daily_agent.context import get_agent_context
from color_it_daily_agent.lib.persistence import update_document, get_local_output_dir

logger = logging.getLogger(__name__)


class PromptTracePlugin(BasePlugin):
    """
    ADK Plugin that captures all prompts, system instructions, model responses, 
    and tool execution traces across the agent pipeline.

    Also prunes stale intermediate tool context logs across agents in a SequentialAgent pipeline
    to drastically cut token usage and latency.

    - Local Mode (no_persist=True): Saves traces to `./tmp/color_it_daily/<doc_id>/prompt_trace.json`
      and updates the local `document.json`.
    - Cloud Mode (no_persist=False): Appends trace entries into the `"traces"` array on the existing
      Firestore document for this run (`coloring_pages/<doc_id>`).
    """

    def __init__(self, name: str = "PromptTracePlugin"):
        super().__init__(name=name)

    def _prune_stale_tool_context(self, contents: list) -> list:
        """Strips out intermediate inter-agent tool call logs injected by ADK for previous agents."""
        if not contents:
            return contents

        pruned_contents = []
        for content in contents:
            if not hasattr(content, "parts") or not content.parts:
                pruned_contents.append(content)
                continue

            new_parts = []
            for part in content.parts:
                text = getattr(part, "text", "") or ""
                # Strip tool call and tool result context injected by ADK for previous agents
                if text.startswith("For context:\n["):
                    if "called tool `" in text or "` tool returned result:" in text:
                        continue
                new_parts.append(part)

            if new_parts:
                try:
                    from google.genai import types
                    role = getattr(content, "role", "user") or "user"
                    pruned_contents.append(types.Content(role=role, parts=new_parts))
                except Exception:
                    pruned_contents.append(content)

        return pruned_contents if pruned_contents else contents

    def _record_trace(self, trace_entry: Dict[str, Any]) -> None:
        ctx = get_agent_context()
        if not ctx:
            logger.debug("PromptTracePlugin: No active AgentContext found; skipping trace record.")
            return

        doc_id = ctx.document_id
        no_persist = ctx.no_persist

        # 1. Always save locally to document output directory
        local_dir = get_local_output_dir(doc_id)
        local_trace_path = os.path.join(local_dir, "prompt_trace.json")

        try:
            traces = []
            if os.path.exists(local_trace_path):
                with open(local_trace_path, "r", encoding="utf-8") as f:
                    traces = json.load(f)
            traces.append(trace_entry)
            with open(local_trace_path, "w", encoding="utf-8") as f:
                json.dump(traces, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to append to local prompt_trace.json for '{doc_id}': {e}")

        # 2. Update document.json or Firestore with ArrayUnion
        if no_persist:
            try:
                update_document(doc_id, {"traces": traces}, no_persist=True)
            except Exception as e:
                logger.error(f"Failed to update local document.json with trace: {e}")
        else:
            try:
                from color_it_daily_agent.lib.database import get_db
                from color_it_daily_agent.app_configs import configs

                db = get_db()
                doc_ref = db.collection(configs.coloring_page_collection).document(doc_id)
                doc_ref.set(
                    {"traces": firestore.ArrayUnion([trace_entry]), "updated_at": datetime.now(timezone.utc)},
                    merge=True,
                )
                logger.info(f"📍 [TRACE LOGGED] Appended {trace_entry.get('event')} trace to Firestore doc '{doc_id}'")
            except Exception as e:
                logger.error(f"Failed to append trace to Firestore for doc '{doc_id}': {e}")

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> Optional[LlmResponse]:
        """Prunes stale tool context and captures model request."""
        try:
            if llm_request.contents:
                llm_request.contents = self._prune_stale_tool_context(llm_request.contents)
        except Exception as e:
            logger.error(f"PromptTracePlugin: Error pruning context: {e}")

        sys_instruction = None
        if llm_request.config and llm_request.config.system_instruction:
            sys_instruction = str(llm_request.config.system_instruction)

        contents_summary = []
        if llm_request.contents:
            for content in llm_request.contents:
                parts_str = []
                if hasattr(content, "parts") and content.parts:
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            parts_str.append(part.text)
                        elif hasattr(part, "function_call") and part.function_call:
                            parts_str.append(f"FunctionCall: {part.function_call.name}")
                        elif hasattr(part, "function_response") and part.function_response:
                            parts_str.append(f"FunctionResponse: {part.function_response.name}")
                contents_summary.append({
                    "role": getattr(content, "role", "user"),
                    "parts": parts_str
                })

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "LLM_REQUEST",
            "agent": callback_context.agent_name,
            "model": llm_request.model or "default",
            "system_instruction": sys_instruction,
            "contents": contents_summary,
        }
        self._record_trace(entry)
        return None

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> Optional[LlmResponse]:
        """Captures model output response and tool calls."""
        output_text = None
        function_calls = []

        if llm_response.content and llm_response.content.parts:
            for part in llm_response.content.parts:
                if getattr(part, "text", None):
                    output_text = part.text
                if getattr(part, "function_call", None):
                    function_calls.append({
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args) if part.function_call.args else {}
                    })

        tokens = {}
        if llm_response.usage_metadata:
            tokens = {
                "input_tokens": getattr(llm_response.usage_metadata, "prompt_token_count", 0),
                "output_tokens": getattr(llm_response.usage_metadata, "candidates_token_count", 0),
            }

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "LLM_RESPONSE",
            "agent": callback_context.agent_name,
            "output_text": output_text,
            "function_calls": function_calls,
            "tokens": tokens,
            "error_message": llm_response.error_message if llm_response.error_code else None
        }
        self._record_trace(entry)
        return None

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict]:
        """Captures tool start and arguments."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "TOOL_START",
            "agent": tool_context.agent_name,
            "tool_name": tool.name,
            "arguments": tool_args,
        }
        self._record_trace(entry)
        return None

    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict,
    ) -> Optional[dict]:
        """Captures tool completion and result."""
        result_str = str(result)
        if len(result_str) > 2000:
            result_str = result_str[:2000] + "... [truncated]"

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "TOOL_COMPLETE",
            "agent": tool_context.agent_name,
            "tool_name": tool.name,
            "result_snippet": result_str,
        }
        self._record_trace(entry)
        return None
