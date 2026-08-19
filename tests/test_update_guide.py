from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "update_guide.py"
SPEC = importlib.util.spec_from_file_location("update_guide", SCRIPT_PATH)
assert SPEC and SPEC.loader
update_guide = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(update_guide)


class FakeHeaders:
    def get_content_charset(self) -> str:
        return "utf-8"

    def get(self, name: str, default: str | None = None) -> str | None:
        return default


class FakeResponse:
    def __init__(self, body: str) -> None:
        self.body = body.encode("utf-8")
        self.headers = FakeHeaders()

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class UpdateGuideTests(unittest.TestCase):
    def assert_invalid_update_preserves_cache(self, source: str) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            references = Path(temp_dir)
            html_path = references / "guide.html"
            markdown_path = references / "guide.md"
            state_path = references / ".update-state.json"
            html_path.write_text("原有 HTML", encoding="utf-8")
            markdown_path.write_text("原有 Markdown", encoding="utf-8")

            with (
                patch.object(update_guide, "HTML_PATH", html_path),
                patch.object(update_guide, "MARKDOWN_PATH", markdown_path),
                patch.object(update_guide, "STATE_PATH", state_path),
                patch.object(update_guide, "urlopen", return_value=FakeResponse(source)),
                patch.object(sys, "argv", ["update_guide.py", "--force"]),
            ):
                result = update_guide.main()

            self.assertEqual(result, 0)
            self.assertEqual(html_path.read_text(encoding="utf-8"), "原有 HTML")
            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "原有 Markdown")

    def test_current_official_page_passes_validation(self) -> None:
        source = (ROOT / "references" / "guide.html").read_text(encoding="utf-8")

        markdown = update_guide.build_validated_markdown(source, "2026-08-19T00:00:00+08:00")

        self.assertEqual(markdown.count("\n| ---"), 14)
        self.assertEqual(markdown.count("```javascript\n"), 4)
        self.assertIn("### 3.3 postNote — 发布笔记", markdown)
        self.assertIn("### 4.2 已禁用的行为", markdown)

    def test_valid_page_updates_html_and_markdown_cache(self) -> None:
        source = (ROOT / "references" / "guide.html").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as temp_dir:
            references = Path(temp_dir)
            html_path = references / "guide.html"
            markdown_path = references / "guide.md"
            state_path = references / ".update-state.json"

            with (
                patch.object(update_guide, "HTML_PATH", html_path),
                patch.object(update_guide, "MARKDOWN_PATH", markdown_path),
                patch.object(update_guide, "STATE_PATH", state_path),
                patch.object(update_guide, "urlopen", return_value=FakeResponse(source)),
                patch.object(sys, "argv", ["update_guide.py", "--force"]),
            ):
                result = update_guide.main()

            self.assertEqual(result, 0)
            self.assertEqual(html_path.read_text(encoding="utf-8"), source)
            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("### 3.2 API 一览", markdown)
            self.assertIn("### 4.2 已禁用的行为", markdown)

    def test_error_page_does_not_overwrite_existing_cache(self) -> None:
        self.assert_invalid_update_preserves_cache("<html><body>系统错误</body></html>")

    def test_guide_missing_core_api_section_does_not_overwrite_cache(self) -> None:
        source = (ROOT / "references" / "guide.html").read_text(encoding="utf-8")
        incomplete_source = source.replace("3.2 API 一览", "3.2 接口目录")

        self.assert_invalid_update_preserves_cache(incomplete_source)

    def test_guide_missing_forbidden_behavior_section_does_not_overwrite_cache(self) -> None:
        source = (ROOT / "references" / "guide.html").read_text(encoding="utf-8")
        incomplete_source = source.replace("4.2 已禁用的行为", "4.2 行为说明")

        self.assert_invalid_update_preserves_cache(incomplete_source)

    def test_guide_with_broken_tables_does_not_overwrite_cache(self) -> None:
        source = (ROOT / "references" / "guide.html").read_text(encoding="utf-8")
        broken_source = source.replace("<table", "<div").replace("</table>", "</div>")

        self.assert_invalid_update_preserves_cache(broken_source)

    def test_guide_with_broken_code_examples_does_not_overwrite_cache(self) -> None:
        source = (ROOT / "references" / "guide.html").read_text(encoding="utf-8")
        broken_source = source.replace('<pre class="code">', "<div>").replace("</pre>", "</div>")

        self.assert_invalid_update_preserves_cache(broken_source)

    def test_not_modified_response_does_not_rebuild_from_invalid_html_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            references = Path(temp_dir)
            html_path = references / "guide.html"
            markdown_path = references / "guide.md"
            state_path = references / ".update-state.json"
            html_path.write_text("损坏的 HTML 缓存", encoding="utf-8")
            markdown_path.write_text("仍然有效的 Markdown 缓存", encoding="utf-8")
            not_modified = HTTPError(update_guide.SOURCE_URL, 304, "未变更", None, None)

            with (
                patch.object(update_guide, "HTML_PATH", html_path),
                patch.object(update_guide, "MARKDOWN_PATH", markdown_path),
                patch.object(update_guide, "STATE_PATH", state_path),
                patch.object(update_guide, "urlopen", side_effect=not_modified),
                patch.object(sys, "argv", ["update_guide.py", "--force"]),
            ):
                result = update_guide.main()

            self.assertEqual(result, 0)
            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "仍然有效的 Markdown 缓存")


if __name__ == "__main__":
    unittest.main()
