import sys
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

# Provide mocks for optional dependencies in test environment
class MockModule(MagicMock):
    __path__ = []
    __spec__ = None

for mod in [
    "psycopg2", "psycopg2.pool", "psycopg2.errors",
    "dotenv", "tenacity",
    "google", "google.cloud", "google.cloud.firestore",
    "google.cloud.firestore_v1", "google.cloud.firestore_v1.vector",
    "google.genai", "google.genai.types",
    "google.adk", "google.adk.tools", "google.adk.tools.tool_context",
    "google.adk.tools.base_tool", "google.adk.plugins",
    "google.adk.plugins.base_plugin", "google.adk.agents",
    "google.adk.agents.callback_context", "google.adk.models",
]:
    if mod not in sys.modules:
        m = MockModule()
        sys.modules[mod] = m

class MockProgrammingError(Exception): pass
class MockUndefinedColumn(MockProgrammingError): pass
sys.modules["psycopg2"].ProgrammingError = MockProgrammingError
sys.modules["psycopg2"].errors.UndefinedColumn = MockUndefinedColumn
sys.modules["tenacity"].retry = lambda *a, **kw: (lambda f: f)
class BasePlugin:
    def __init__(self, name=None): self.name = name
sys.modules["google.adk.plugins.base_plugin"].BasePlugin = BasePlugin

import psycopg2
from color_it_daily_agent.creative_director.instructions import SEO_COPY_RULES, get_creative_director_instructions
from color_it_daily_agent.lib.postgres import add_new_page
from color_it_daily_agent.context import AgentContext, set_agent_context
from color_it_daily_agent.critic.tools.publish import _validate_seo_fields, publish_to_firestore
from color_it_daily_agent.lib.trace_plugin import extract_creative_director_json


class TestSeoCopyRules(unittest.TestCase):
    def test_seo_copy_rules_constant_exists_and_content(self):
        """Verifies SEO_COPY_RULES is a non-empty string defining the required SEO guidelines."""
        self.assertIsInstance(SEO_COPY_RULES, str)
        self.assertIn("long_description", SEO_COPY_RULES)
        self.assertIn("meta_description", SEO_COPY_RULES)
        self.assertIn("target_keyword", SEO_COPY_RULES)
        self.assertIn("80–150 words", SEO_COPY_RULES)
        self.assertIn("140–160 characters", SEO_COPY_RULES)

    def test_cd_instructions_include_seo_fields(self):
        """Verifies get_creative_director_instructions includes SEO fields and rules."""
        instructions = get_creative_director_instructions(target_keyword="cute dinosaur coloring page")
        self.assertIn("long_description", instructions)
        self.assertIn("meta_description", instructions)
        self.assertIn("target_keyword", instructions)
        self.assertIn("cute dinosaur coloring page", instructions)


class TestAddNewPageOrderSafety(unittest.TestCase):
    def setUp(self):
        self.mock_cursor = MagicMock()
        def execute_side_effect(query, params=None):
            if "RETURNING" in str(query):
                self.mock_cursor.fetchone.return_value = (42,)
                self.mock_cursor.fetchone.side_effect = None
            else:
                self.mock_cursor.fetchone.return_value = None
                self.mock_cursor.fetchone.side_effect = psycopg2.ProgrammingError("no results to fetch")
            return None
        self.mock_cursor.execute.side_effect = execute_side_effect

    def test_add_new_page_with_seo_columns_success(self):
        """When columns exist in PostgreSQL, INSERT with SEO columns succeeds."""
        page_data = {
            "name": "Dinosaur Sandcastle",
            "full_path": "https://storage.googleapis.com/test/full.webp",
            "thumbnail_path": "https://storage.googleapis.com/test/thumb.webp",
            "prompt": "A cute dinosaur building a sandcastle on the beach.",
            "tags": ["dinosaur", "beach", "sandcastle"],
            "long_description": "A delightful coloring page featuring a smiling dinosaur building a sandcastle on a sunny summer beach.",
            "meta_description": "Free printable dinosaur sandcastle coloring page for kids. Enjoy coloring a friendly dinosaur on the beach.",
            "target_keyword": "dinosaur sandcastle coloring page",
        }

        with patch("color_it_daily_agent.lib.postgres.get_page_unique_name", return_value="dinosaur-sandcastle"), \
             patch("color_it_daily_agent.lib.postgres.ensure_tags_exist", return_value=[("dinosaur", 1), ("beach", 2)]):
            page_id = add_new_page(self.mock_cursor, page_data)

        self.assertEqual(page_id, 42)
        # Verify SAVEPOINT and RELEASE SAVEPOINT were called
        execute_calls = [c[0][0] for c in self.mock_cursor.execute.call_args_list]
        self.assertIn("SAVEPOINT seo_insert", execute_calls)
        self.assertIn("RELEASE SAVEPOINT seo_insert", execute_calls)

    def test_add_new_page_order_safety_fallback_on_undefined_column(self):
        """When columns do not exist yet (error 42703 / UndefinedColumn), falls back to INSERT without SEO columns."""
        page_data = {
            "name": "Dinosaur Sandcastle",
            "full_path": "https://storage.googleapis.com/test/full.webp",
            "thumbnail_path": "https://storage.googleapis.com/test/thumb.webp",
            "prompt": "A cute dinosaur building a sandcastle on the beach.",
            "tags": ["dinosaur"],
            "long_description": "A delightful coloring page featuring a smiling dinosaur building a sandcastle.",
            "meta_description": "Free printable dinosaur sandcastle coloring page for kids.",
            "target_keyword": "dinosaur sandcastle coloring page",
        }

        # Simulate UndefinedColumn error on first insert with SEO columns
        err = psycopg2.ProgrammingError('column "long_description" of relation "pages" does not exist')
        setattr(err, "pgcode", "42703")

        call_count = 0
        def fake_execute(query, params=None):
            nonlocal call_count
            call_count += 1
            if "long_description" in str(query):
                raise err
            if "RETURNING" in str(query):
                self.mock_cursor.fetchone.return_value = (42,)
                self.mock_cursor.fetchone.side_effect = None
            else:
                self.mock_cursor.fetchone.return_value = None
                self.mock_cursor.fetchone.side_effect = psycopg2.ProgrammingError("no results to fetch")
            return None

        self.mock_cursor.execute.side_effect = fake_execute

        with patch("color_it_daily_agent.lib.postgres.get_page_unique_name", return_value="dinosaur-sandcastle"), \
             patch("color_it_daily_agent.lib.postgres.ensure_tags_exist", return_value=[("dinosaur", 1)]):
            page_id = add_new_page(self.mock_cursor, page_data)

        self.assertEqual(page_id, 42)


class TestPublishValidation(unittest.TestCase):
    def test_word_count_boundaries(self):
        """Verifies boundaries for long_description: 79 (invalid), 80 (valid), 150 (valid), 151 (invalid)."""
        words_79 = "word " * 79
        val_79, _, _ = _validate_seo_fields(long_description=words_79)
        self.assertIsNone(val_79)

        words_80 = "word " * 80
        val_80, _, _ = _validate_seo_fields(long_description=words_80)
        self.assertIsNotNone(val_80)
        self.assertEqual(val_80, words_80.strip())

        words_150 = "word " * 150
        val_150, _, _ = _validate_seo_fields(long_description=words_150)
        self.assertIsNotNone(val_150)
        self.assertEqual(val_150, words_150.strip())

        words_151 = "word " * 151
        val_151, _, _ = _validate_seo_fields(long_description=words_151)
        self.assertIsNone(val_151)

    def test_char_count_boundaries(self):
        """Verifies boundaries for meta_description: 119 (invalid), 120 (valid), 170 (valid), 171 (invalid)."""
        chars_119 = "a" * 119
        _, val_119, _ = _validate_seo_fields(meta_description=chars_119)
        self.assertIsNone(val_119)

        chars_120 = "a" * 120
        _, val_120, _ = _validate_seo_fields(meta_description=chars_120)
        self.assertIsNotNone(val_120)
        self.assertEqual(val_120, chars_120)

        chars_170 = "a" * 170
        _, val_170, _ = _validate_seo_fields(meta_description=chars_170)
        self.assertIsNotNone(val_170)
        self.assertEqual(val_170, chars_170)

        chars_171 = "a" * 171
        _, val_171, _ = _validate_seo_fields(meta_description=chars_171)
        self.assertIsNone(val_171)

    def test_none_and_empty_input(self):
        """Verifies None, empty string, and whitespace-only inputs return None without raising."""
        val_long, val_meta, val_kw = _validate_seo_fields(None, None, None)
        self.assertIsNone(val_long)
        self.assertIsNone(val_meta)
        self.assertIsNone(val_kw)

        val_long, val_meta, val_kw = _validate_seo_fields("", "", "")
        self.assertIsNone(val_long)
        self.assertIsNone(val_meta)
        self.assertIsNone(val_kw)

        val_long, val_meta, val_kw = _validate_seo_fields("   ", "   ", "   ")
        self.assertIsNone(val_long)
        self.assertIsNone(val_meta)
        self.assertIsNone(val_kw)

    def test_target_keyword_normalization(self):
        """Verifies target_keyword is stripped and lowercased."""
        _, _, kw = _validate_seo_fields(target_keyword="  Cute Dinosaur Coloring Page  ")
        self.assertEqual(kw, "cute dinosaur coloring page")

    def test_never_raises_on_invalid_types(self):
        """Verifies unexpected input types do not raise exceptions."""
        val_long, val_meta, val_kw = _validate_seo_fields(long_description=12345, meta_description=True)
        self.assertIsNone(val_long)
        self.assertIsNone(val_meta)


class TestExtractCreativeDirectorJson(unittest.TestCase):
    def test_case_1_fenced_json_block(self):
        """Case 1: JSON wrapped in ```json ... ``` code fence."""
        raw = """Here is my proposal for the page:
```json
{
  "long_description": "A delightful coloring page featuring a smiling dinosaur.",
  "meta_description": "Free printable dinosaur coloring page for kids of all ages.",
  "target_keyword": "dinosaur coloring page"
}
```
Hope you like it!"""
        result = extract_creative_director_json(raw)
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("target_keyword"), "dinosaur coloring page")
        self.assertEqual(result.get("long_description"), "A delightful coloring page featuring a smiling dinosaur.")

    def test_case_2_bare_json(self):
        """Case 2: Bare JSON string with no fences or conversational filler."""
        raw = '{"long_description": "Bare json description", "meta_description": "Bare json meta", "target_keyword": "bare json kw"}'
        result = extract_creative_director_json(raw)
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("target_keyword"), "bare json kw")

    def test_case_3_substring_braces(self):
        """Case 3: JSON inside conversational text without fences (extracted by first { to last })."""
        raw = 'Some text before {"long_description": "Substring desc", "meta_description": "Substring meta", "target_keyword": "substring kw"} some text after.'
        result = extract_creative_director_json(raw)
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("target_keyword"), "substring kw")
        self.assertEqual(result.get("long_description"), "Substring desc")

    def test_case_4_failure_logs_warning_and_returns_none(self):
        """Case 4: Failed parse logs at WARNING and returns None."""
        invalid_raw = "This response contains no valid JSON object anywhere."
        with self.assertLogs("color_it_daily_agent.lib.trace_plugin", level="WARNING") as cm:
            result = extract_creative_director_json(invalid_raw)
        self.assertIsNone(result)
        self.assertTrue(any("Could not parse CreativeDirector output" in log for log in cm.output))


class TestPublishSeoPrecedence(unittest.TestCase):
    def test_cd_context_wins_over_critic_tool_args(self):
        """Creative Director's saved context values win over Critic's tool args."""
        ctx = AgentContext(
            document_id="test-doc-1",
            current_date="2026-10-18",
            collection_name="coloring_pages",
            no_persist=True,
            agent_version="test-1.0",
            long_description="word " * 100,
            meta_description="m" * 140,
            target_keyword="cd target keyword",
        )
        set_agent_context(ctx)

        critic_long = "critic " * 100
        critic_meta = "c" * 140
        critic_kw = "critic target keyword"

        with patch("color_it_daily_agent.critic.tools.publish.update_document") as mock_update:
            publish_to_firestore(
                title="Test Page",
                reasoning="Test reasoning",
                description="Test description",
                visual_tags=["test"],
                mood="happy",
                target_audience="kids",
                positive_prompt="test prompt",
                optimized_image_path="test.png",
                status="approved",
                feedback="looks good",
                long_description=critic_long,
                meta_description=critic_meta,
                target_keyword=critic_kw,
            )

            mock_update.assert_called_once()
            payload = mock_update.call_args[0][1]
            self.assertEqual(payload["long_description"], ("word " * 100).strip())
            self.assertEqual(payload["meta_description"], "m" * 140)
            self.assertEqual(payload["target_keyword"], "cd target keyword")

    def test_critic_tool_args_fallback_when_context_empty(self):
        """Critic's tool args are used as fallback when Creative Director context values are missing or empty."""
        ctx = AgentContext(
            document_id="test-doc-2",
            current_date="2026-10-18",
            collection_name="coloring_pages",
            no_persist=True,
            agent_version="test-1.0",
            long_description=None,
            meta_description="",
            target_keyword=None,
        )
        set_agent_context(ctx)

        critic_long = "critic " * 100
        critic_meta = "c" * 140
        critic_kw = "critic target keyword"

        with patch("color_it_daily_agent.critic.tools.publish.update_document") as mock_update:
            publish_to_firestore(
                title="Test Page",
                reasoning="Test reasoning",
                description="Test description",
                visual_tags=["test"],
                mood="happy",
                target_audience="kids",
                positive_prompt="test prompt",
                optimized_image_path="test.png",
                status="approved",
                feedback="looks good",
                long_description=critic_long,
                meta_description=critic_meta,
                target_keyword=critic_kw,
            )

            mock_update.assert_called_once()
            payload = mock_update.call_args[0][1]
            self.assertEqual(payload["long_description"], critic_long.strip())
            self.assertEqual(payload["meta_description"], critic_meta)
            self.assertEqual(payload["target_keyword"], "critic target keyword")


if __name__ == "__main__":
    unittest.main()
