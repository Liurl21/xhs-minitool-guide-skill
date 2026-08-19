from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCHES = {
    "references/answering.md",
    "references/development.md",
    "references/review-debug.md",
}


class ProgressiveDisclosureTests(unittest.TestCase):
    def test_skill_points_to_each_task_branch(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")

        for pointer in EXPECTED_BRANCHES:
            self.assertRegex(skill, rf"`{re.escape(pointer)}`")
            self.assertTrue((ROOT / pointer).is_file(), pointer)

    def test_each_branch_points_to_the_official_guide_cache(self) -> None:
        for pointer in EXPECTED_BRANCHES:
            content = (ROOT / pointer).read_text(encoding="utf-8")
            self.assertIn("guide.md", content, pointer)


if __name__ == "__main__":
    unittest.main()
