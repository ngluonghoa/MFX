"""Synthetic negative tests for the high-confidence RE4c secret signature check."""
import tempfile
import unittest
from pathlib import Path
from subprocess import run

from tools.check_repo_secrets import scan_bytes, scan_repository


class RepositorySecretScanTests(unittest.TestCase):
    def test_tracked_python_text_without_signatures_is_clean(self):
        self.assertEqual(scan_bytes(b"print('ok')\n"), ())

    def test_github_pat_detected_without_echoing(self):
        synthetic = ("gh" + "p_" + ("A" * 36)).encode()
        self.assertIn("GITHUB_CLASSIC_PAT", scan_bytes(synthetic))
        self.assertNotIn(synthetic.decode(), repr(scan_bytes(synthetic)))

    def test_github_fine_grained_pat_detected(self):
        synthetic = ("github_" + "pat_" + ("A" * 24)).encode()
        self.assertIn("GITHUB_FINE_GRAINED_PAT", scan_bytes(synthetic))

    def test_aws_key_id_detected(self):
        synthetic = ("AK" + "IA" + "A" * 16).encode()
        self.assertIn("AWS_ACCESS_KEY_ID", scan_bytes(synthetic))

    def test_pem_private_key_detected(self):
        synthetic = ("-----BEGIN " + "PRIVATE KEY-----").encode()
        self.assertIn("PRIVATE_KEY_PEM", scan_bytes(synthetic))

    def test_google_api_key_detected(self):
        synthetic = ("AI" + "za" + "A" * 35).encode()
        self.assertIn("GOOGLE_API_KEY", scan_bytes(synthetic))

    def test_slack_token_detected(self):
        synthetic = ("xox" + "b-" + "A" * 22).encode()
        self.assertIn("SLACK_TOKEN", scan_bytes(synthetic))

    def test_stripe_live_key_detected(self):
        synthetic = ("sk_" + "live_" + "A" * 26).encode()
        self.assertIn("STRIPE_LIVE_SECRET", scan_bytes(synthetic))

    def test_untracked_secret_not_scanned_and_not_claimed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(["git", "-C", str(root), "init", "-q"], check=True)
            (root / "tracked.txt").write_text("SAFE\n", encoding="utf-8")
            (root / "untracked.txt").write_text("not scanned\n", encoding="utf-8")
            run(["git", "-C", str(root), "add", "tracked.txt"], check=True)
            count, findings = scan_repository(root)
            self.assertEqual((count, findings), (1, ()))

    def test_tracked_binary_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(["git", "-C", str(root), "init", "-q"], check=True)
            (root / "binary.dat").write_bytes(b"\x00\xff")
            run(["git", "-C", str(root), "add", "binary.dat"], check=True)
            count, findings = scan_repository(root)
            self.assertEqual(count, 0)
            self.assertEqual(findings, (("binary.dat", "UNREADABLE_OR_NONTEXT"),))


if __name__ == "__main__":
    unittest.main()
