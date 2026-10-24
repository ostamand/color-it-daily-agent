import asyncio
import json
import logging
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import httpx

import main
from color_it_daily_agent.lib.retry_utils import (
    log_model_retry,
    extract_error_code,
)


class MockAPIError(Exception):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


class TestSingleFlight(unittest.TestCase):
    def setUp(self):
        # Ensure clean in-flight state before each test
        main._in_flight_runs.clear()

    def tearDown(self):
        main._in_flight_runs.clear()

    def test_extract_error_code(self):
        """Verify error code extraction from status codes, attributes, and messages."""
        self.assertEqual(extract_error_code(MockAPIError("Quota exceeded", 429)), 429)
        self.assertEqual(extract_error_code(MockAPIError("Unavailable", 503)), 503)
        self.assertEqual(extract_error_code(Exception("RESOURCE_EXHAUSTED: quota limit")), 429)
        self.assertEqual(extract_error_code(ValueError("invalid")), "ValueError")
        self.assertIsNone(extract_error_code(None))

    def test_log_model_retry_logs_warning_with_attempt_and_code(self):
        """Verifies that log_model_retry logs a WARNING with attempt number and error code."""
        mock_retry_state = MagicMock()
        mock_retry_state.attempt_number = 2
        mock_retry_state.outcome.exception.return_value = MockAPIError("Resource exhausted", 429)
        mock_retry_state.next_action.sleep = 15.0
        mock_retry_state.fn.__name__ = "generate_coloring_page"

        with patch("color_it_daily_agent.lib.retry_utils.logger.warning") as mock_warn:
            log_model_retry(mock_retry_state)
            mock_warn.assert_called_once()
            log_msg = mock_warn.call_args[0][0]
            self.assertIn("attempt 2", log_msg)
            self.assertIn("code: 429", log_msg)
            self.assertIn("generate_coloring_page", log_msg)
            self.assertIn("15.0s", log_msg)

    def test_concurrent_run_for_same_session_executes_once(self):
        """
        Verifies that two concurrent POST /run requests for the same session_id
        join the single-flight execution and only invoke the pipeline once.
        """
        pipeline_call_count = 0

        async def slow_run_async(*args, **kwargs):
            nonlocal pipeline_call_count
            pipeline_call_count += 1
            await asyncio.sleep(0.2)
            if False:
                yield None

        async def run_concurrent():
            session_id = "test-session-single-flight-1"
            payload = {
                "app_name": "color_it_daily_agent",
                "user_id": "daily-job",
                "session_id": session_id,
                "new_message": {
                    "role": "user",
                    "parts": [{"text": json.dumps({"document_id": "doc-uuid-1"})}],
                },
            }

            with patch("main.prepare_agent_execution") as mock_prep, patch(
                "google.adk.runners.Runner.run_async", side_effect=slow_run_async
            ), patch("main.get_document_status", return_value="PASS"):
                mock_ctx = MagicMock()
                mock_ctx.document_id = "doc-uuid-1"
                mock_ctx.no_persist = True
                mock_prep.return_value = (mock_ctx, {"document_id": "doc-uuid-1"})

                transport = httpx.ASGITransport(app=main.app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    resp1, resp2 = await asyncio.gather(
                        client.post("/run", json=payload),
                        client.post("/run", json=payload),
                    )

                self.assertEqual(resp1.status_code, 200)
                self.assertEqual(resp2.status_code, 200)
                self.assertEqual(resp1.content, resp2.content)
                self.assertEqual(pipeline_call_count, 1)
                self.assertEqual(mock_prep.call_count, 1)

        asyncio.run(run_concurrent())
        self.assertEqual(len(main._in_flight_runs), 0, "In-flight registry must be empty after completion")

    def test_concurrent_run_for_same_document_id_executes_once(self):
        """
        Verifies that two concurrent POST /run requests sharing the same document_id
        (even with different session IDs) are guarded by single-flight.
        """
        pipeline_call_count = 0

        async def slow_run_async(*args, **kwargs):
            nonlocal pipeline_call_count
            pipeline_call_count += 1
            await asyncio.sleep(0.2)
            if False:
                yield None

        async def run_concurrent():
            payload1 = {
                "app_name": "color_it_daily_agent",
                "user_id": "daily-job",
                "session_id": "session-A",
                "new_message": {
                    "role": "user",
                    "parts": [{"text": json.dumps({"document_id": "shared-doc-123"})}],
                },
            }
            payload2 = {
                "app_name": "color_it_daily_agent",
                "user_id": "daily-job",
                "session_id": "session-B",
                "new_message": {
                    "role": "user",
                    "parts": [{"text": json.dumps({"document_id": "shared-doc-123"})}],
                },
            }

            with patch("main.prepare_agent_execution") as mock_prep, patch(
                "google.adk.runners.Runner.run_async", side_effect=slow_run_async
            ), patch("main.get_document_status", return_value="PASS"):
                mock_ctx = MagicMock()
                mock_ctx.document_id = "shared-doc-123"
                mock_ctx.no_persist = True
                mock_prep.return_value = (mock_ctx, {"document_id": "shared-doc-123"})

                transport = httpx.ASGITransport(app=main.app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    resp1, resp2 = await asyncio.gather(
                        client.post("/run", json=payload1),
                        client.post("/run", json=payload2),
                    )

                self.assertEqual(resp1.status_code, 200)
                self.assertEqual(resp2.status_code, 200)
                self.assertEqual(resp1.content, resp2.content)
                self.assertEqual(pipeline_call_count, 1)
                self.assertEqual(mock_prep.call_count, 1)

        asyncio.run(run_concurrent())
        self.assertEqual(len(main._in_flight_runs), 0, "In-flight registry must be clean")

    def test_duplicate_run_logs_warning(self):
        """Verifies that a warning log line is produced when a duplicate run is detected."""
        async def slow_run_async(*args, **kwargs):
            await asyncio.sleep(0.15)
            if False:
                yield None

        async def run_concurrent():
            session_id = "duplicate-log-session"
            payload = {
                "app_name": "color_it_daily_agent",
                "user_id": "daily-job",
                "session_id": session_id,
                "new_message": {
                    "role": "user",
                    "parts": [{"text": json.dumps({"document_id": "doc-log-1"})}],
                },
            }

            with patch("main.prepare_agent_execution") as mock_prep, patch(
                "google.adk.runners.Runner.run_async", side_effect=slow_run_async
            ), patch("main.get_document_status", return_value="PASS"), patch(
                "main.logger.warning"
            ) as mock_warn:
                mock_ctx = MagicMock()
                mock_ctx.document_id = "doc-log-1"
                mock_ctx.no_persist = True
                mock_prep.return_value = (mock_ctx, {"document_id": "doc-log-1"})

                transport = httpx.ASGITransport(app=main.app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    await asyncio.gather(
                        client.post("/run", json=payload),
                        client.post("/run", json=payload),
                    )

                # Ensure warning was called for the duplicate run
                duplicate_warnings = [
                    c[0][0] for c in mock_warn.call_args_list
                    if "Duplicate in-flight /run request detected" in str(c[0][0])
                ]
                self.assertTrue(
                    len(duplicate_warnings) >= 1,
                    f"Expected duplicate warning log but got: {mock_warn.call_args_list}",
                )

        asyncio.run(run_concurrent())

    def test_in_flight_cleanup_on_error(self):
        """Verifies that if a run raises an exception, in-flight state is cleaned up."""
        async def failing_run_async(*args, **kwargs):
            raise RuntimeError("Underlying pipeline failure")
            if False:
                yield None

        async def run_test():
            session_id = "failing-session-cleanup"
            payload = {
                "app_name": "color_it_daily_agent",
                "user_id": "daily-job",
                "session_id": session_id,
                "new_message": {
                    "role": "user",
                    "parts": [{"text": json.dumps({"document_id": "failing-doc"})}],
                },
            }

            with patch("main.prepare_agent_execution") as mock_prep, patch(
                "google.adk.runners.Runner.run_async", side_effect=failing_run_async
            ), patch("main.mark_document_failed"):
                mock_ctx = MagicMock()
                mock_ctx.document_id = "failing-doc"
                mock_ctx.no_persist = True
                mock_prep.return_value = (mock_ctx, {"document_id": "failing-doc"})

                transport = httpx.ASGITransport(app=main.app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post("/run", json=payload)
                    self.assertEqual(resp.status_code, 500)
                    self.assertIn("Underlying pipeline failure", resp.text)

            self.assertEqual(len(main._in_flight_runs), 0, "In-flight registry must be cleaned up on error")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
