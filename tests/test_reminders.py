"""Tests for the reminders/settings additions (ADR-008).

These do NOT touch the real systemd user bus. The subprocess + systemctl
boundary in recordward.reminders is patched so we can verify the unit-file
generation and the settings wiring deterministically on any platform.
"""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rwrem-")
        os.environ["RECORDWARD_HOME"] = self.tmp
        # Keep systemd units inside the temp dir too, via XDG_CONFIG_HOME.
        self.cfg = os.path.join(self.tmp, "cfg")
        os.environ["XDG_CONFIG_HOME"] = self.cfg

        import recordward.paths as paths
        import recordward.settings as settings
        import recordward.reminders as reminders

        importlib.reload(paths)
        self.settings = importlib.reload(settings)
        self.reminders = importlib.reload(reminders)

    def tearDown(self):
        os.environ.pop("RECORDWARD_HOME", None)
        os.environ.pop("XDG_CONFIG_HOME", None)
        for root, _, files in os.walk(self.tmp, topdown=False):
            for f in files:
                Path(root, f).unlink()
            Path(root).rmdir()


class TestSettings(Base):
    def test_new_keys_have_defaults(self):
        s = self.settings.load()
        self.assertEqual(s["reminders"], "off")
        self.assertFalse(s["setup_complete"])
        self.assertEqual(s["idle_shutdown_minutes"], 15)

    def test_reminders_value_is_validated(self):
        self.settings.set_value("reminders", "garbage")
        self.assertEqual(self.settings.load()["reminders"], "off")
        self.settings.set_value("reminders", "weekly")
        self.assertEqual(self.settings.load()["reminders"], "weekly")

    def test_idle_minutes_bounded(self):
        self.settings.set_value("idle_shutdown_minutes", 99999)
        self.assertLessEqual(self.settings.load()["idle_shutdown_minutes"], 1440)
        self.settings.set_value("idle_shutdown_minutes", -5)
        self.assertGreaterEqual(self.settings.load()["idle_shutdown_minutes"], 0)


class TestReminderUnits(Base):
    def test_install_writes_units_and_enables(self):
        calls = []

        def fake_run(cmd, *a, **k):
            calls.append(cmd)
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(self.reminders, "supported", return_value=True), \
             mock.patch.object(self.reminders.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(self.reminders.shutil, "which", return_value="/usr/bin/recordward"):
            self.reminders.install("weekly")

        unit_dir = Path(self.cfg) / "systemd" / "user"
        timer = (unit_dir / "recordward-reminder.timer").read_text()
        service = (unit_dir / "recordward-reminder.service").read_text()
        self.assertIn("OnCalendar=Mon", timer)
        self.assertIn("Persistent=true", timer)
        self.assertIn("ExecStart=/usr/bin/recordward notify", service)
        # it ran daemon-reload and enable --now
        joined = [" ".join(c) for c in calls]
        self.assertTrue(any("daemon-reload" in c for c in joined))
        self.assertTrue(any("enable" in c and "--now" in c for c in joined))

    def test_monthly_calendar(self):
        with mock.patch.object(self.reminders, "supported", return_value=True), \
             mock.patch.object(self.reminders.subprocess, "run",
                               return_value=mock.Mock(returncode=0, stdout="")), \
             mock.patch.object(self.reminders.shutil, "which", return_value="/usr/bin/recordward"):
            self.reminders.install("monthly")
        timer = (Path(self.cfg) / "systemd" / "user" / "recordward-reminder.timer").read_text()
        self.assertIn("OnCalendar=*-*-01", timer)

    def test_uninstall_removes_units(self):
        unit_dir = Path(self.cfg) / "systemd" / "user"
        unit_dir.mkdir(parents=True, exist_ok=True)
        (unit_dir / "recordward-reminder.timer").write_text("x")
        (unit_dir / "recordward-reminder.service").write_text("x")
        with mock.patch.object(self.reminders, "supported", return_value=True), \
             mock.patch.object(self.reminders.subprocess, "run",
                               return_value=mock.Mock(returncode=0, stdout="")):
            self.reminders.uninstall()
        self.assertFalse((unit_dir / "recordward-reminder.timer").exists())
        self.assertFalse((unit_dir / "recordward-reminder.service").exists())

    def test_apply_off_calls_uninstall(self):
        with mock.patch.object(self.reminders, "uninstall") as u:
            self.reminders.apply("off")
            u.assert_called_once()

    def test_install_rejects_bad_cadence(self):
        with mock.patch.object(self.reminders, "supported", return_value=True):
            with self.assertRaises(ValueError):
                self.reminders.install("yearly")


if __name__ == "__main__":
    unittest.main()
