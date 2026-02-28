import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from audit_log import log_audit_event, tail_audit_events
from retention import rotate_audit_if_needed, run_housekeeping


class TestAuditLog(unittest.TestCase):
    def test_tail_audit_events_returns_last_n(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_file = Path(tmp) / "audit.jsonl"

            for idx in range(1, 6):
                log_audit_event(
                    event_type=f"event_{idx}",
                    actor="system",
                    details={"idx": idx},
                    audit_file_path=audit_file,
                )

            events = tail_audit_events(3, audit_file_path=audit_file)
            self.assertEqual(len(events), 3)
            self.assertEqual([event["event_type"] for event in events], ["event_3", "event_4", "event_5"])


class TestRetention(unittest.TestCase):
    def test_rotate_audit_if_needed(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_file = Path(tmp) / "audit.jsonl"
            audit_file.write_text("x" * 120, encoding="utf-8")

            rotated = rotate_audit_if_needed(audit_file, max_bytes=100, backups=2)
            self.assertTrue(rotated)
            self.assertTrue((Path(tmp) / "audit.jsonl.1").exists())
            self.assertTrue(audit_file.exists())
            self.assertEqual(audit_file.read_text(encoding="utf-8"), "")

    def test_run_housekeeping_prunes_old_files_and_rotates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs_dir = root / "logs"
            audit_dir = root / "audit"
            logs_dir.mkdir(parents=True, exist_ok=True)
            audit_dir.mkdir(parents=True, exist_ok=True)

            old_log = logs_dir / "old.log"
            old_log.write_text("old", encoding="utf-8")
            old_ts = time.time() - (3 * 24 * 60 * 60)
            os.utime(old_log, (old_ts, old_ts))

            audit_file = audit_dir / "audit.jsonl"
            audit_file.write_text("x" * 300, encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "MAYMUNAI_LOG_DIR": str(logs_dir),
                    "MAYMUNAI_AUDIT_DIR": str(audit_dir),
                    "MAYMUNAI_LOG_RETENTION_DAYS": "1",
                    "MAYMUNAI_AUDIT_RETENTION_DAYS": "1",
                    "MAYMUNAI_AUDIT_MAX_BYTES": "100",
                    "MAYMUNAI_AUDIT_BACKUPS": "3",
                },
                clear=False,
            ):
                report = run_housekeeping()

            self.assertGreaterEqual(report["removed_logs"], 1)
            self.assertEqual(report["rotated_audit"], 1)
            self.assertFalse(old_log.exists())
            self.assertTrue((audit_dir / "audit.jsonl.1").exists())


if __name__ == "__main__":
    unittest.main()

