import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

import main


class TestAutoCreateSession(unittest.TestCase):
    def test_app_server_auto_create_session_is_enabled(self):
        """Verifies that main.app is configured with auto_create_session=True on the ADK server."""
        run_route = next(
            r for r in main.app.routes if getattr(r, "path", None) == "/run"
        )
        closure_dict = dict(
            zip(
                run_route.endpoint.__code__.co_freevars,
                [c.cell_contents for c in run_route.endpoint.__closure__],
            )
        )
        server = closure_dict["self"]
        self.assertTrue(
            server.auto_create_session,
            "ADK server auto_create_session must be True to prevent 404 on missing sessions across container instances",
        )

    def test_post_run_with_unknown_session_does_not_return_404(self):
        """Verifies that POST /run with an unknown session ID does not return 404 'Session not found'.
        
        Mocks external service dependencies (Firestore preparation and Gemini runner execution)
        to prevent calls to real external APIs during unit testing.
        """
        async def dummy_run_async(*args, **kwargs):
            if False:
                yield None

        with patch("main.prepare_agent_execution") as mock_prep, patch(
            "google.adk.runners.Runner.run_async", side_effect=dummy_run_async
        ):
            mock_prep.return_value = (None, {})
            client = TestClient(main.app)
            response = client.post(
                "/run",
                json={
                    "app_name": "color_it_daily_agent",
                    "user_id": "daily-job",
                    "session_id": "nonexistent-session-autoscaled-instance-uuid",
                    "new_message": {"parts": [{"text": "{}"}]},
                },
            )

            self.assertNotEqual(
                response.status_code,
                404,
                f"POST /run returned 404: {response.text}",
            )
            self.assertEqual(
                response.status_code,
                200,
                f"Expected 200 OK but received {response.status_code}: {response.text}",
            )


if __name__ == "__main__":
    unittest.main()
