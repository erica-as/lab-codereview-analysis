import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawler import dedupe_pr_rows, reached_eligible_cap


class RepoCapLogicTests(unittest.TestCase):
    def test_reached_eligible_cap(self) -> None:
        self.assertFalse(reached_eligible_cap(99, 100))
        self.assertTrue(reached_eligible_cap(100, 100))

    def test_dedupe_pr_rows_by_repo_and_number(self) -> None:
        rows = [
            {"repository": "a/b", "number": 10, "title": "old"},
            {"repository": "a/b", "number": 10, "title": "new"},
            {"repository": "a/b", "number": 11, "title": "keep"},
            {"repository": "c/d", "number": 10, "title": "also-keep"},
        ]

        result = dedupe_pr_rows(rows)
        self.assertEqual(len(result), 3)

        result_by_key = {(r["repository"], int(r["number"])): r for r in result}
        self.assertEqual(result_by_key[("a/b", 10)]["title"], "new")
        self.assertEqual(result_by_key[("a/b", 11)]["title"], "keep")
        self.assertEqual(result_by_key[("c/d", 10)]["title"], "also-keep")


if __name__ == "__main__":
    unittest.main()
