import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from github_client import GitHubClient


class FakeResponse:
    def __init__(self, status_code, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

    def json(self):
        return {}


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)

    def request(self, method, url, params=None, timeout=30):
        return self._responses.pop(0)


class TestableGitHubClient(GitHubClient):
    def __init__(self, responses):
        super().__init__(token="")
        self._fake_session = FakeSession(responses)

    def _session(self):
        return self._fake_session


class GitHubClientRetryTests(unittest.TestCase):
    def test_parse_retry_after_bounds_and_invalid(self):
        client = GitHubClient(token="")
        self.assertEqual(client._parse_retry_after("9999"), 300)
        self.assertEqual(client._parse_retry_after("0"), 1)
        self.assertIsNone(client._parse_retry_after("abc"))

    def test_compute_backoff_grows_with_attempt(self):
        client = GitHubClient(token="")
        with patch("github_client.random.uniform", return_value=0.0):
            self.assertEqual(client._compute_backoff_seconds(0), 1.0)
            self.assertEqual(client._compute_backoff_seconds(1), 2.0)
            self.assertEqual(client._compute_backoff_seconds(2), 4.0)

    def test_retries_on_403_abuse_without_retry_after(self):
        responses = [
            FakeResponse(403, text="You have triggered an abuse detection mechanism."),
            FakeResponse(200, text="ok"),
        ]
        client = TestableGitHubClient(responses)

        with patch("github_client.random.uniform", return_value=0.0):
            with patch("github_client.time.sleep") as mock_sleep:
                result = client.request("GET", "https://api.github.com/example", max_retries=2)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(mock_sleep.call_count, 1)


if __name__ == "__main__":
    unittest.main()
