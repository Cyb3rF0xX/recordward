"""Core-logic tests: scheduling, status, data management, note hygiene.

Run: python -m unittest discover -s tests  (from the repo root)

Every test runs against an isolated RECORDWARD_HOME temp dir, so the suite never
touches your real data. Because core.py reads its path constants at import
time, we point RECORDWARD_HOME at a temp dir and reload the module per test.
"""

from __future__ import annotations

import datetime as dt
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bgtest-")
        os.environ["RECORDWARD_HOME"] = self.tmp
        # Import fresh so module-level SCHEDULE/LOG/... point at self.tmp.
        import recordward.paths as paths
        import recordward.core as core

        importlib.reload(paths)
        self.core = importlib.reload(core)
        self.core.bootstrap()

    def tearDown(self):
        os.environ.pop("RECORDWARD_HOME", None)
        for root, _, files in os.walk(self.tmp, topdown=False):
            for f in files:
                Path(root, f).unlink()
            Path(root).rmdir()


class TestSchedule(Base):
    def test_bootstrap_seeds_default_schedule(self):
        self.assertTrue(self.core.SCHEDULE.exists())
        sources = self.core.load_sources()
        self.assertEqual(len(sources), 10)
        self.assertTrue(all("name" in s and "every_days" in s for s in sources))

    def test_load_sources_self_heals_when_missing(self):
        self.core.SCHEDULE.unlink()
        sources = self.core.load_sources()  # should reseed, not crash
        self.assertEqual(len(sources), 10)


class TestStatus(Base):
    def _src(self, every=30, name="X"):
        return {"name": name, "every_days": every, "url": "", "notes": ""}

    def test_never_requested_is_due(self):
        st = self.core.status_for(self._src(), [])
        self.assertTrue(st["due"])
        self.assertIsNone(st["last"])

    def test_recent_request_not_due(self):
        today = self.core.today()
        log = [{"name": "X", "date": today.isoformat()}]
        st = self.core.status_for(self._src(every=30), log)
        self.assertFalse(st["due"])
        self.assertEqual(st["next_due"], today + dt.timedelta(days=30))

    def test_old_request_is_due_again(self):
        old = (self.core.today() - dt.timedelta(days=40)).isoformat()
        log = [{"name": "X", "date": old}]
        st = self.core.status_for(self._src(every=30), log)
        self.assertTrue(st["due"])

    def test_snooze_defers_due(self):
        future = (self.core.today() + dt.timedelta(days=10)).isoformat()
        log = [{"name": "X", "snooze_until": future}]
        st = self.core.status_for(self._src(), log)
        self.assertFalse(st["due"])
        self.assertTrue(st["snoozed"])


class TestRecording(Base):
    def test_record_done_writes_log_and_history(self):
        self.core.record_done("Equifax (AnnualCreditReport)", "found nothing")
        log = self.core.load_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["note"], "found nothing")
        self.assertTrue(self.core.HISTORY.exists())

    def test_record_snooze_returns_future_date(self):
        until = self.core.record_snooze("Equifax (AnnualCreditReport)", 30)
        self.assertEqual(until, self.core.today() + dt.timedelta(days=30))


class TestNoteHygiene(Base):
    def test_newlines_collapsed(self):
        # log injection attempt: a note that looks like a second log line
        cleaned = self.core._clean_note("ok\n2020-01-01 FAKE ENTRY")
        self.assertNotIn("\n", cleaned)

    def test_length_capped(self):
        cleaned = self.core._clean_note("x" * 10_000)
        self.assertLessEqual(len(cleaned), self.core.MAX_NOTE_LEN + 1)

    def test_blank_becomes_none(self):
        self.assertIsNone(self.core._clean_note("   "))
        self.assertIsNone(self.core._clean_note(None))


class TestDataManagement(Base):
    def test_reset_history_removes_logs(self):
        self.core.record_done("Equifax (AnnualCreditReport)", None)
        self.core.reset_history()
        self.assertFalse(self.core.LOG.exists())
        self.assertFalse(self.core.HISTORY.exists())

    def test_reset_snoozes_keeps_real_requests(self):
        self.core.record_done("Equifax (AnnualCreditReport)", None)
        self.core.record_snooze("Experian (AnnualCreditReport)", 30)
        self.core.reset_snoozes()
        log = self.core.load_log()
        self.assertTrue(any(e.get("date") for e in log))  # request kept
        self.assertFalse(any(e.get("snooze_until") for e in log))  # snooze gone

    def test_reset_schedule_restores_default(self):
        self.core.SCHEDULE.write_text("sources:\n", encoding="utf-8")
        self.core.reset_schedule()
        self.assertEqual(len(self.core.load_sources()), 10)

    def test_reset_all_wipes_everything(self):
        self.core.record_done("Equifax (AnnualCreditReport)", None)
        self.core.reset_all()
        for f in (self.core.LOG, self.core.HISTORY, self.core.SCHEDULE):
            self.assertFalse(f.exists(), f"{f} should be gone")


if __name__ == "__main__":
    unittest.main()
