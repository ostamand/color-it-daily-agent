import logging
from typing import Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


def is_rate_limit_or_transient_error(exception: Exception) -> bool:
    """
    Returns True if exception is a 429 Rate Limit / Quota / Resource Exhausted error,
    or a 503/504 transient server error.
    """
    code = getattr(exception, "code", None) or getattr(exception, "status_code", None)
    if code in (429, 500, 502, 503, 504):
        return True

    err_str = str(exception).upper()
    if any(k in err_str for k in ("429", "RESOURCE_EXHAUSTED", "QUOTA", "RATE LIMIT", "503", "UNAVAILABLE")):
        return True

    return False


retry_genai_call = retry(
    retry=retry_if_exception(is_rate_limit_or_transient_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=3, min=5, max=60),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
