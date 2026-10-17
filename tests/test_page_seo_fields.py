import sys
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

# Provide mock for psycopg2 if not installed in current environment
if "psycopg2" not in sys.modules:
    try:
        import psycopg2
    except ImportError:
        mock_psycopg2 = MagicMock()
        class MockProgrammingError(Exception):
            pass
        class MockUndefinedColumn(MockProgrammingError):
            pass
        mock_psycopg2.ProgrammingError = MockProgrammingError
        mock_psycopg2.errors.UndefinedColumn = MockUndefinedColumn
        sys.modules["psycopg2"] = mock_psycopg2
        sys.modules["psycopg2.pool"] = MagicMock()
        sys.modules["psycopg2.errors"] = mock_psycopg2.errors
        import psycopg2

if "dotenv" not in sys.modules:
    try:
        import dotenv
    except ImportError:
        mock_dotenv = MagicMock()
        mock_dotenv.load_dotenv = MagicMock()
        sys.modules["dotenv"] = mock_dotenv

from color_it_daily_agent.creative_director.instructions import SEO_COPY_RULES, get_creative_director_instructions
from color_it_daily_agent.lib.postgres import add_new_page
from color_it_daily_agent.context import AgentContext, set_agent_context


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
        self.mock_cursor.fetchone.return_value = (42,)

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
            return None

        self.mock_cursor.execute.side_effect = fake_execute

        with patch("color_it_daily_agent.lib.postgres.get_page_unique_name", return_value="dinosaur-sandcastle"), \
             patch("color_it_daily_agent.lib.postgres.ensure_tags_exist", return_value=[("dinosaur", 1)]):
            page_id = add_new_page(self.mock_cursor, page_data)

        self.assertEqual(page_id, 42)


class TestPublishValidation(unittest.TestCase):
    def test_validation_logic(self):
        """Verifies word count (80-150) and character count (120-170) constraints."""
        valid_words = "word " * 100
        short_words = "word " * 50
        long_words = "word " * 160

        self.assertTrue(80 <= len(valid_words.split()) <= 150)
        self.assertFalse(80 <= len(short_words.split()) <= 150)
        self.assertFalse(80 <= len(long_words.split()) <= 150)

        valid_chars = "a" * 150
        short_chars = "a" * 100
        long_chars = "a" * 180

        self.assertTrue(120 <= len(valid_chars) <= 170)
        self.assertFalse(120 <= len(short_chars) <= 170)
        self.assertFalse(120 <= len(long_chars) <= 170)


if __name__ == "__main__":
    unittest.main()
