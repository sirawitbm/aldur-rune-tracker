import unittest
from unittest.mock import patch

from src.update_checker import ReleaseInfo, fetch_newer_release, newer_release, parse_version


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"tag_name":"v0.1.3","draft":false,"prerelease":false}'


class UpdateCheckerTests(unittest.TestCase):
    def test_parse_version_accepts_release_tags(self):
        self.assertEqual(parse_version("v1.2.30"), (1, 2, 30))
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))

    def test_parse_version_rejects_non_release_tags(self):
        self.assertIsNone(parse_version("v1.2"))
        self.assertIsNone(parse_version("v1.2.3-beta"))

    def test_returns_newer_stable_release(self):
        payload = {
            "tag_name": "v0.1.3",
            "html_url": "https://github.com/example/releases/tag/v0.1.3",
            "draft": False,
            "prerelease": False,
        }
        self.assertEqual(
            newer_release(payload, "0.1.2"),
            ReleaseInfo(
                "0.1.3",
                "https://github.com/sirawitbm/aldur-rune-tracker/releases/tag/v0.1.3",
            ),
        )

    def test_ignores_equal_or_older_release(self):
        payload = {
            "tag_name": "v0.1.2",
            "html_url": "https://github.com/example/releases/tag/v0.1.2",
        }
        self.assertIsNone(newer_release(payload, "0.1.2"))
        self.assertIsNone(newer_release(payload, "0.1.3"))

    def test_ignores_draft_and_prerelease(self):
        base = {
            "tag_name": "v0.2.0",
            "html_url": "https://github.com/example/releases/tag/v0.2.0",
        }
        self.assertIsNone(newer_release({**base, "draft": True}, "0.1.2"))
        self.assertIsNone(newer_release({**base, "prerelease": True}, "0.1.2"))

    def test_fetch_uses_github_api_and_timeout(self):
        with patch("src.update_checker.urllib.request.urlopen", return_value=_Response()) as urlopen:
            release = fetch_newer_release("0.1.2", timeout_sec=4)

        request = urlopen.call_args.args[0]
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 4)
        self.assertEqual(request.host, "api.github.com")
        self.assertEqual(request.headers["User-agent"], "AldurRuneTracker-update-check")
        self.assertEqual(release.version, "0.1.3")


if __name__ == "__main__":
    unittest.main()