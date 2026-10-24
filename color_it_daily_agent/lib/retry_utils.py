import logging
from typing import Any, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
    RetryCallState,
)

logger = logging.getLogger(__name__)


def is_429_error(exception: BaseException) -> bool:
    """
    Returns True if exception represents an HTTP 429 / RESOURCE_EXHAUSTED rate limit or quota error.

    Checks real error codes (e.g. google.genai.errors.APIError / ClientError .code == 429),
    walks __cause__ and __context__ chains, checks google.api_core ResourceExhausted,
    and falls back to explicit 'RESOURCE_EXHAUSTED' status strings.
    Explicitly avoids bare '429' substring matching to prevent false positives on UUIDs.
    """
    if exception is None:
        return False

    # Collect known exception classes safely
    check_classes = []
    try:
        from google.genai.errors import APIError
        check_classes.append(APIError)
    except ImportError:
        pass

    try:
        from google.api_core.exceptions import ResourceExhausted, TooManyRequests
        check_classes.extend([ResourceExhausted, TooManyRequests])
    except ImportError:
        pass

    visited = set()
    current: Optional[BaseException] = exception
    while current is not None and id(current) not in visited:
        visited.add(id(current))

        # Check known class instances
        if check_classes and any(isinstance(current, cls) for cls in check_classes):
            code = getattr(current, "code", None) or getattr(current, "status_code", None)
            if code == 429 or type(current).__name__ in ("ResourceExhausted", "TooManyRequests", "_ResourceExhaustedError"):
                return True

        # Check code / status_code attributes directly on any exception
        code = getattr(current, "code", None) or getattr(current, "status_code", None)
        if code == 429:
            return True

        # Check exception type name
        type_name = type(current).__name__
        if type_name in ("ResourceExhausted", "TooManyRequests", "_ResourceExhaustedError"):
            return True

        # Walk exception chain
        current = current.__cause__ or current.__context__

    # Explicit string fallback for RESOURCE_EXHAUSTED status (no bare '429' substring)
    err_str = str(exception)
    if "RESOURCE_EXHAUSTED" in err_str:
        return True

    return False


def is_rate_limit_or_transient_error(exception: Exception) -> bool:
    """
    Returns True if exception is a 429 Rate Limit / Quota / Resource Exhausted error,
    or a 503/504 transient server error.
    """
    if is_429_error(exception):
        return True

    visited = set()
    current: Optional[BaseException] = exception
    while current is not None and id(current) not in visited:
        visited.add(id(current))

        code = getattr(current, "code", None) or getattr(current, "status_code", None)
        if code in (500, 502, 503, 504):
            return True

        current = current.__cause__ or current.__context__

    err_str = str(exception).upper()
    if any(k in err_str for k in ("RESOURCE_EXHAUSTED", "QUOTA", "RATE LIMIT", "503", "UNAVAILABLE")):
        return True

    return False


def extract_error_code(exc: Optional[BaseException]) -> Optional[Any]:
    """
    Extracts HTTP status code, numeric error code, or exception type name
    from an exception or its causes for structured log reporting.
    """
    if exc is None:
        return None
    visited = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        code = getattr(current, "code", None) or getattr(current, "status_code", None)
        if code:
            return code
        type_name = type(current).__name__
        if type_name in ("ResourceExhausted", "TooManyRequests", "_ResourceExhaustedError"):
            return 429
        current = current.__cause__ or current.__context__
    if "RESOURCE_EXHAUSTED" in str(exc):
        return 429
    return type(exc).__name__


def log_model_retry(retry_state: RetryCallState) -> None:
    """
    Logs model retry attempts at WARNING level with attempt number and error code
    so long runs and retry backoffs can be explained from logs.
    """
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    attempt = retry_state.attempt_number
    sleep_sec = f"{retry_state.next_action.sleep:.1f}" if retry_state.next_action else "0"
    code = extract_error_code(exc)
    fn_name = getattr(retry_state.fn, "__name__", str(retry_state.fn))
    logger.warning(
        f"⚠️ Model retry attempt {attempt} for '{fn_name}' after error (code: {code}): {exc}. "
        f"Backing off for {sleep_sec}s..."
    )


retry_genai_call = retry(
    retry=retry_if_exception(is_rate_limit_or_transient_error),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=5, min=10, max=120),
    before_sleep=log_model_retry,
    reraise=True,
)
