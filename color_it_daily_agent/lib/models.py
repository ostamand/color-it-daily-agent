"""
Shared Gemini model initialization for Color It Daily Agent.

Configures default model instances with HTTP retry options for transient
errors (429 Rate Limit / RESOURCE_EXHAUSTED and 503 Service Unavailable).
"""

from typing import Optional
from google.adk.models import Gemini
from google.genai import types

from ..app_configs import configs


def get_default_llm_model(model_name: Optional[str] = None) -> Gemini:
    """
    Returns a Gemini model instance configured with retry options for transient errors.
    
    Retries up to 5 attempts with exponential backoff on HTTP 429 and 503.
    """
    return Gemini(
        model=model_name or configs.llm_model,
        retry_options=types.HttpRetryOptions(
            attempts=5,
            initial_delay=5,
            max_delay=60,
            exp_base=2,
            http_status_codes=[429, 503],
        ),
    )
