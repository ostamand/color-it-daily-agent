import sys
import unittest
from unittest.mock import MagicMock

# Provide mocks for optional dependencies in test environment
if "tenacity" not in sys.modules:
    mock_tenacity = MagicMock()
    mock_tenacity.retry = lambda *a, **kw: (lambda f: f)
    sys.modules["tenacity"] = mock_tenacity

from color_it_daily_agent.lib.retry_utils import is_429_error, is_rate_limit_or_transient_error


class MockAPIError(Exception):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


class MockClientError(Exception):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


class ResourceExhausted(Exception):
    pass


class TestErrorClassifier(unittest.TestCase):
    def test_apierror_code_429_returns_true(self):
        """APIError with code 429 should be classified as 429."""
        err = MockAPIError("Resource exhausted", 429)
        self.assertTrue(is_429_error(err))

    def test_clienterror_code_429_returns_true(self):
        """ClientError with code 429 should be classified as 429."""
        err = MockClientError("Rate limit exceeded", 429)
        self.assertTrue(is_429_error(err))

    def test_uuid_containing_429_returns_false(self):
        """Error message containing a document UUID with substring '429' should NOT be classified as 429."""
        err = Exception("Failed document dbb7f7e8-429a-4a7b-b006-0cdd099cdadd: unexpected state")
        self.assertFalse(is_429_error(err))

        err2 = RuntimeError("Error processing document 123429abcd: syntax error")
        self.assertFalse(is_429_error(err2))

    def test_resource_exhausted_string_fallback_returns_true(self):
        """Exception containing RESOURCE_EXHAUSTED in message should be classified as 429."""
        err = Exception("Status: RESOURCE_EXHAUSTED: Quota exceeded for metric")
        self.assertTrue(is_429_error(err))

    def test_resource_exhausted_class_returns_true(self):
        """ResourceExhausted exception class should be classified as 429."""
        err = ResourceExhausted("Vertex AI quota exhausted")
        self.assertTrue(is_429_error(err))

    def test_chained_cause_with_429_returns_true(self):
        """Chained exception with __cause__ having code 429 should be classified as 429."""
        cause = MockAPIError("Vertex AI 429 Rate Limit", 429)
        try:
            raise RuntimeError("Agent pipeline failed during generation") from cause
        except RuntimeError as wrapper:
            self.assertTrue(is_429_error(wrapper))

    def test_chained_context_with_429_returns_true(self):
        """Chained exception with __context__ having code 429 should be classified as 429."""
        try:
            try:
                raise MockAPIError("Vertex AI 429 Rate Limit", 429)
            except MockAPIError:
                raise RuntimeError("Handler failed during error recovery")
        except RuntimeError as wrapper:
            self.assertTrue(is_429_error(wrapper))

    def test_non_429_errors_return_false(self):
        """Non-429 errors should not be classified as 429."""
        self.assertFalse(is_429_error(MockAPIError("Internal Server Error", 500)))
        self.assertFalse(is_429_error(MockAPIError("Not Found", 404)))
        self.assertFalse(is_429_error(ValueError("Invalid argument provided")))
        self.assertFalse(is_429_error(None))

    def test_rate_limit_or_transient_error_helper(self):
        """Verify is_rate_limit_or_transient_error correctly catches 429 and transient 5xx."""
        # 429 errors
        self.assertTrue(is_rate_limit_or_transient_error(MockAPIError("Rate limited", 429)))
        self.assertTrue(is_rate_limit_or_transient_error(ResourceExhausted("Quota")))

        # Transient server errors
        self.assertTrue(is_rate_limit_or_transient_error(MockAPIError("Service Unavailable", 503)))
        self.assertTrue(is_rate_limit_or_transient_error(MockAPIError("Gateway Timeout", 504)))

        # False on UUIDs containing 429
        self.assertFalse(is_rate_limit_or_transient_error(Exception("Failed document dbb7f7e8-429a-4a7b-b006-0cdd099cdadd")))


if __name__ == "__main__":
    unittest.main()
