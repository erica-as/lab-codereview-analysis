import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from checkpoint_store import CheckpointStore


class CheckpointStoreTests(unittest.TestCase):
    def test_checkpoint_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_path = Path(tmpdir) / "checkpoint.json"
            store = CheckpointStore(str(checkpoint_path))

            state = store.get_repo_state("octocat/hello-world")
            self.assertEqual(state["status"], "pending")
            self.assertEqual(state["next_page"], 1)
            self.assertEqual(state["eligible_count"], 0)

            store.update_repo_state(
                "octocat/hello-world",
                status="in_progress",
                next_page=3,
                eligible_count=12,
            )

            reloaded = CheckpointStore(str(checkpoint_path))
            state = reloaded.get_repo_state("octocat/hello-world")
            self.assertEqual(state["status"], "in_progress")
            self.assertEqual(state["next_page"], 3)
            self.assertEqual(state["eligible_count"], 12)

            reloaded.update_repo_state(
                "octocat/hello-world",
                status="done",
                next_page=7,
                eligible_count=100,
                exhausted=False,
                error="",
            )

            final = CheckpointStore(str(checkpoint_path))
            done_state = final.get_repo_state("octocat/hello-world")
            self.assertEqual(done_state["status"], "done")
            self.assertEqual(done_state["next_page"], 7)
            self.assertEqual(done_state["eligible_count"], 100)
            self.assertFalse(done_state["exhausted"])
            self.assertEqual(done_state["error"], "")


if __name__ == "__main__":
    unittest.main()
