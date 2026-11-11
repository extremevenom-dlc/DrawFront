import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import updater as up  # noqa: E402

REPO = "me/DrawFont"
PAYLOAD = {
    "tag_name": "v1.2.0", "body": "New stuff", "html_url": "https://github.com/me/DrawFont/releases/tag/v1.2.0",
    "assets": [
        {"name": "DrawFont-Setup.exe", "browser_download_url": f"https://github.com/{REPO}/releases/download/v1.2.0/DrawFont-Setup.exe", "size": 10},
        {"name": "DrawFont-Android.apk", "browser_download_url": f"https://github.com/{REPO}/releases/download/v1.2.0/DrawFont-Android.apk", "size": 5},
    ],
}


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def opener_returning(body):
    calls = []

    def op(req, timeout=None):
        calls.append(req.full_url)
        return Resp(body)
    op.calls = calls
    return op


class VersionTests(unittest.TestCase):
    def test_parse_and_compare(self):
        self.assertEqual(up.parse_version("v1.10.2-beta"), (1, 10, 2))
        self.assertTrue(up.is_newer("1.10.0", "1.9.9"))      # numeric, not text, comparison
        self.assertTrue(up.is_newer("v2", "1.9.9"))
        self.assertFalse(up.is_newer("1.1.0", "1.1"))
        self.assertFalse(up.is_newer("1.0.0", "1.1.0"))
        self.assertFalse(up.is_newer("garbage", "1.0.0"))
        self.assertTrue(up.is_newer("1.0.1", "0.0.0"))       # dev build 0.0.0 is older than any release


class FetchTests(unittest.TestCase):
    def test_fetch_latest(self):
        op = opener_returning(json.dumps(PAYLOAD).encode())
        rel = up.fetch_latest(REPO, opener=op)
        self.assertEqual(op.calls, [f"https://api.github.com/repos/{REPO}/releases/latest"])
        self.assertEqual(rel["version"], "1.2.0")
        self.assertEqual(up.pick_asset(rel, up.INSTALLER_NAME)["size"], 10)
        self.assertIsNone(up.pick_asset(rel, "nope.exe"))

    def test_no_releases_yet_is_not_an_error(self):
        def op(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)
        self.assertIsNone(up.fetch_latest(REPO, opener=op))

    def test_errors_become_updateerror(self):
        def offline(req, timeout=None):
            raise urllib.error.URLError("no network")

        def limited(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 403, "rate", {}, None)
        with self.assertRaises(up.UpdateError):
            up.fetch_latest(REPO, opener=offline)
        with self.assertRaises(up.UpdateError):
            up.fetch_latest(REPO, opener=limited)
        with self.assertRaises(up.UpdateError):
            up.fetch_latest(REPO, opener=opener_returning(b"<html>not json"))


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = os.path.join(self.tmp.name, "setup.exe")
        self.url = PAYLOAD["assets"][0]["browser_download_url"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_good_download(self):
        seen = []
        up.download(self.url, self.dest, REPO, expected_size=10, opener=opener_returning(b"0123456789"), progress=seen.append)
        with open(self.dest, "rb") as f:
            self.assertEqual(f.read(), b"0123456789")
        self.assertEqual(seen[-1], 10)
        self.assertFalse(os.path.exists(self.dest + ".part"))

    def test_wrong_size_rejected_and_cleaned_up(self):
        with self.assertRaises(up.UpdateError):
            up.download(self.url, self.dest, REPO, expected_size=10, opener=opener_returning(b"short"))
        self.assertFalse(os.path.exists(self.dest))
        self.assertFalse(os.path.exists(self.dest + ".part"))

    def test_foreign_urls_refused_without_any_request(self):
        op = opener_returning(b"x")
        for bad in ("https://evil.example/DrawFont-Setup.exe",
                    "http://github.com/me/DrawFont/releases/download/v1/x.exe",
                    "https://github.com/other/DrawFont/releases/download/v1/x.exe",
                    "https://github.com/me/DrawFont-evil/releases/download/v1/x.exe"):
            with self.assertRaises(up.UpdateError):
                up.download(bad, self.dest, REPO, opener=op)
        self.assertEqual(op.calls, [])

    def test_run_installer_is_quiet_and_detached(self):
        got = {}
        up.run_installer("C:/x/setup.exe", popen=lambda cmd, **kw: got.update(cmd=cmd, kw=kw))
        self.assertEqual(got["cmd"][0], "C:/x/setup.exe")
        self.assertIn("/SILENT", got["cmd"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
