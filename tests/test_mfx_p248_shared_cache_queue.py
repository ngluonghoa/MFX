"""P248: one shared cache lock with non-replacing pending queue."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"
EXPECTED = frozenset((
    "mfx-b3b-sealed-index.yml",
    "mfx-b3b-synthetic-drive-proof.yml",
    "mfx-hot-cache.yml",
    "mfx-hourly-cache-audit.yml",
    "mfx-m5-h4-parity-readonly.yml",
    "mfx-native-htf-cache-audit.yml",
    "mfx-native-htf-drive-commit.yml",
    "mfx-native-htf-incremental-commit.yml",
    "mfx-native-htf-incremental-preview.yml",
    "mfx-native-htf-manual-probe.yml",
    "mfx-oauth-drive-bootstrap.yml",
    "mfx-v1-manual-drive-six-tf-readonly.yml",
    "mfx-warm-promotion.yml",
    "twelve-data-cache.yml",
))
CRONS = {
    "twelve-data-cache.yml": "10 * * * *",
    "mfx-hot-cache.yml": "15 * * * *",
    "mfx-native-htf-incremental-commit.yml": "25 * * * *",
    "mfx-hourly-cache-audit.yml": "35 * * * *",
    "mfx-native-htf-cache-audit.yml": "45 * * * *",
    "mfx-m5-h4-parity-readonly.yml": "55 0 * * *",
}


def shared_workflows() -> dict[str, str]:
    result = {}
    for path in ROOT.glob("*.yml"):
        content = path.read_text(encoding="utf-8")
        match = re.search(r"(?m)^concurrency:\n((?:  [^\n]+\n)+)", content)
        if match and "mfx-twelvedata-private-cache" in match.group(1):
            result[path.name] = match.group(1)
    return result


class SharedCacheQueueTests(unittest.TestCase):
    def test_all_shared_lock_participants_are_inventoried(self) -> None:
        self.assertEqual(frozenset(shared_workflows()), EXPECTED)

    def test_all_participants_keep_single_running_nonreplacing_pending(self) -> None:
        for name, block in shared_workflows().items():
            with self.subTest(name=name):
                self.assertEqual(block.count("  queue: max\n"), 1)
                self.assertEqual(block.count("  cancel-in-progress: false\n"), 1)
                self.assertNotIn("cancel-in-progress: true", block)
                if name != "mfx-hot-cache.yml":
                    self.assertIn("  group: mfx-twelvedata-private-cache\n", block)
                else:
                    self.assertIn("format('mfx-hot-disabled-{0}', github.run_id)", block)

    def test_schedule_and_manual_entrypoint_unchanged(self) -> None:
        for name in EXPECTED:
            text = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                crons = re.findall(r'(?m)^\s*- cron: "([^"]+)"', text)
                self.assertEqual(crons, [CRONS[name]] if name in CRONS else [])
        manual = (ROOT / "mfx-v1-manual-drive-six-tf-readonly.yml").read_text(
            encoding="utf-8")
        self.assertIn("  workflow_dispatch:", manual)
        self.assertNotIn("\n  push:", manual)
        self.assertNotIn("\n  schedule:", manual)
        self.assertIn("confirm_read_only == 'READ_ONLY_NO_SIGNAL'", manual)
        self.assertIn("MFX_V1_SIX_TF_MANUAL_READONLY_APPROVED == 'true'", manual)
