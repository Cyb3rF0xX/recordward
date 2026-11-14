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
class TestFreeLimits(Base):
    """Provider free-request limits (min_days) and per-company guidance."""
    def test_default_schedule_never_below_provider_limit(self):
        for s in self.core.load_sources():
            self.assertGreaterEqual(
                s["every_days"], s["min_days"], s["name"]
            )
    def test_expected_limits(self):
        by = {s["name"].split(" (")[0]: s for s in self.core.load_sources()}
        for bureau in ("Equifax", "Experian", "TransUnion"):
            self.assertEqual(by[bureau]["min_days"], 7)
        for name in ("LexisNexis Consumer Disclosure Report", "Checkr",
                     "Sterling", "HireRight", "First Advantage",
                     "Accurate Background"):
            self.assertEqual(by[name]["min_days"], 365, name)
            self.assertEqual(by[name]["every_days"], 365, name)
    def test_min_days_defaults_to_zero_for_old_schedules(self):
        self.core.SCHEDULE.write_text(
            'sources:\n  - name: "Old"\n    every_days: 10\n', encoding="utf-8"
        )
        (src,) = self.core.load_sources()
        self.assertEqual(src["min_days"], 0)
    def test_card_warns_when_reminder_shorter_than_limit(self):
        src = {"name": "X", "url": "", "notes": "", "every_days": 30,
               "min_days": 365}
        st = self.core.status_for(src, [])
        html = self.core._card_html(st)
        self.assertIn("limit-warn", html)
        self.assertIn("free limit: once per 365d", html)
    def test_card_has_no_warning_when_ok(self):
        src = {"name": "X", "url": "", "notes": "", "every_days": 365,
               "min_days": 365}
        html = self.core._card_html(self.core.status_for(src, []))
        self.assertNotIn('class="limit-warn"', html)
    def test_every_company_has_request_and_dispute_steps(self):
        for s in self.core.load_sources():
            if s["name"].startswith("CFPB"):
                continue
            text = " ".join(self.core.instructions_for(s["name"])).lower()
            self.assertIn("request", text, s["name"])
            self.assertIn("dispute", text, s["name"])
    def test_credit_bureaus_cover_freeze_alert_and_optout(self):
        for name in ("Equifax (AnnualCreditReport)",
                     "Experian (AnnualCreditReport)",
                     "TransUnion (AnnualCreditReport)"):
            text = " ".join(self.core.instructions_for(name)).lower()
            for word in ("freeze", "fraud alert", "opt out"):
                self.assertIn(word, text, name)
class TestVersion(unittest.TestCase):
    def test_pyproject_and_package_versions_match(self):
        import re
        import recordward
        root = Path(__file__).resolve().parent.parent
        text = (root / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), recordward.__version__)
    def test_version_is_pep440_like(self):
        import re
        import recordward
        self.assertRegex(
            recordward.__version__, r"^\d+\.\d+\.\d+(\.dev\d+|(a|b|rc)\d+)?$"
        )


class TestIcons(unittest.TestCase):
    ASSETS = Path(__file__).resolve().parent.parent / "recordward" / "assets"

    def test_svg_sources_are_wellformed(self):
        import xml.etree.ElementTree as ET
        for n in ("icon.svg", "icon-small.svg"):
            root = ET.parse(self.ASSETS / n).getroot()
            self.assertTrue(root.tag.endswith("svg"), n)

    def test_png_sizes_and_ico_present(self):
        import struct
        png_magic = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])
        for size in (16, 24, 32, 48, 64, 128, 256, 512):
            data = (self.ASSETS / f"icon-{size}.png").read_bytes()
            self.assertEqual(data[:8], png_magic)
            w, h = struct.unpack(">II", data[16:24])
            self.assertEqual((w, h), (size, size))
        ico = (self.ASSETS / "icon.ico").read_bytes()
        self.assertEqual(ico[:4], bytes([0, 0, 1, 0]))

    def test_page_has_favicon_and_logo(self):
        import recordward.core as core
        src = {"name": "X", "url": "", "notes": "", "every_days": 30}
        page = core.render_page([core.status_for(src, [])])
        self.assertIn('rel="icon"', page)
        self.assertIn("data:image/svg+xml;base64,", page)
        self.assertIn('class="logo"', page)

    def test_launcher_html_has_logo(self):
        from recordward import launcher
        self.assertIn('class="logo"', launcher._launcher_html(True))


class TestLaunchScreen(unittest.TestCase):
    def test_launch_screen_has_no_window_controls(self):
        from recordward import launcher
        html = launcher._launcher_html(True)
        self.assertNotIn('id="winctl"', html)
        self.assertNotIn("window_control", html)

    def test_dashboard_still_has_window_controls(self):
        import recordward.core as core
        src = {"name": "X", "url": "", "notes": "", "every_days": 30}
        page = core.render_page([core.status_for(src, [])])
        self.assertIn('id="winctl"', page)

    def test_launcher_is_compact_and_app_is_large(self):
        from recordward import launcher

        class NoScreen:  # no screen info available
            pass

        lw, lh = launcher._launcher_window_size(NoScreen())
        aw, ah = launcher._default_window_size(NoScreen())
        self.assertLess(lw, 600)
        self.assertGreaterEqual(aw, 1000)  # room for 2+ dashboard columns
        self.assertGreater(aw, lw)
        self.assertGreater(ah, lh)

    def test_sizes_clamp_to_small_screens(self):
        from recordward import launcher

        class Scr:
            width, height = 800, 600

        class Wv:
            screens = [Scr()]

        aw, ah = launcher._default_window_size(Wv())
        self.assertLessEqual(aw, 800)
        self.assertLessEqual(ah, 600)


class TestAppLog(Base):
    """Error log for the console-less app (recordward-app.log)."""

    def setUp(self):
        super().setUp()
        import recordward.applog as applog
        self.applog = importlib.reload(applog)

    def tearDown(self):
        self.applog.disable()
        super().tearDown()

    def test_enable_writes_startup_line_in_data_dir(self):
        import recordward.paths as paths
        p = self.applog.enable()
        self.assertEqual(p, paths.app_log_file())
        self.assertTrue(str(p).startswith(self.tmp))
        self.applog.disable()
        text = p.read_text(encoding="utf-8")
        self.assertIn("RecordWard", text)
        self.assertIn("starting", text)

    def test_unhandled_exception_is_logged_with_traceback(self):
        import sys
        p = self.applog.enable()
        hook_calls = []
        self.applog._saved["excepthook"] = lambda *a: hook_calls.append(a)
        try:
            raise ValueError("boom-for-test")
        except ValueError:
            sys.excepthook(*sys.exc_info())
        self.applog.disable()
        text = p.read_text(encoding="utf-8")
        self.assertIn("Unhandled exception", text)
        self.assertIn("ValueError: boom-for-test", text)
        self.assertIn("Traceback", text)
        self.assertEqual(len(hook_calls), 1)  # previous hook still runs

    def test_missing_console_streams_go_to_log(self):
        import sys
        saved = (sys.stdout, sys.stderr)
        sys.stdout = sys.stderr = None
        try:
            p = self.applog.enable()
            sys.stderr.write("webview problem\n")
            print("hello from print")
        finally:
            self.applog.disable()
            sys.stdout, sys.stderr = saved
        text = p.read_text(encoding="utf-8")
        self.assertIn("webview problem", text)
        self.assertIn("hello from print", text)

    def test_disable_restores_hooks(self):
        import sys
        before = sys.excepthook
        self.applog.enable()
        self.assertIsNot(sys.excepthook, before)
        self.applog.disable()
        self.assertIs(sys.excepthook, before)

    def test_log_size_is_capped(self):
        self.assertLessEqual(self.applog.MAX_BYTES * (self.applog.BACKUPS + 1),
                             1024 * 1024)

    def test_where_lists_app_log(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.core.cmd_where()
        self.assertIn("recordward-app.log", buf.getvalue())

    def test_reset_all_removes_app_log(self):
        p = self.applog.enable()
        self.applog.log.warning("something")
        self.applog.disable()
        self.assertTrue(p.exists())
        self.core.reset_all()
        self.assertFalse(p.exists())

    def test_bundle_entry_enables_log(self):
        src = (Path(__file__).resolve().parent.parent / "packaging" / "entry.py"
               ).read_text(encoding="utf-8")
        self.assertIn("applog.enable()", src)


class TestWindowIcon(unittest.TestCase):
    """Regression: a PNG icon crashed the Windows app (System.Drawing.Icon)."""

    def test_windows_gets_ico(self):
        from recordward import launcher
        path = launcher._window_icon("win32")
        self.assertTrue(path.endswith(".ico"))
        self.assertTrue(Path(path).exists())
        self.assertEqual(Path(path).read_bytes()[:4], bytes([0, 0, 1, 0]))

    def test_other_platforms_get_png(self):
        from recordward import launcher
        for plat in ("linux", "darwin"):
            path = launcher._window_icon(plat)
            self.assertTrue(path.endswith(".png"), plat)
            self.assertTrue(Path(path).exists(), plat)


class TestOpenDashboard(unittest.TestCase):
    """_open_dashboard grows the window and navigates; failures are logged."""

    def test_resizes_then_loads_url(self):
        from recordward import launcher
        calls = []

        class W:
            def resize(self, w, h):
                calls.append(("resize", w, h))

            def move(self, x, y):
                pass

            def load_url(self, url):
                calls.append(("load", url))

        class Wv:
            windows = [W()]

        launcher._open_dashboard(Wv(), "http://127.0.0.1:1/")
        self.assertEqual(calls[0][0], "resize")
        self.assertEqual(calls[-1], ("load", "http://127.0.0.1:1/"))

    def test_navigation_is_deferred(self):
        from recordward import launcher
        self.assertGreater(launcher._NAVIGATE_DELAY_S, 0)


class TestGrowHeight(unittest.TestCase):
    """Launch window grows by the hidden content height, capped to screen."""

    class NoScreen:
        pass

    def test_grows_by_extra(self):
        from recordward import launcher
        self.assertEqual(launcher._grown_height(self.NoScreen(), 500, 40), 540)

    def test_never_shrinks_or_trusts_bad_input(self):
        from recordward import launcher
        for bad in (-50, None, "x"):
            self.assertEqual(launcher._grown_height(self.NoScreen(), 500, bad), 500)

    def test_capped_to_screen(self):
        from recordward import launcher

        class Scr:
            width, height = 800, 600

        class Wv:
            screens = [Scr()]

        self.assertEqual(launcher._grown_height(Wv(), 500, 400), 540)  # 90% of 600


class TestInlineScriptsParse(unittest.TestCase):
    """Every inline <script> in our pages must be valid JavaScript.

    A syntax error silently disables a whole page's buttons, and the Python
    tests can't see it. Uses `node --check` (syntax only); skipped without node.
    """

    @staticmethod
    def _scripts(html):
        import re
        return re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.S)

    def _check(self, label, html):
        import shutil
        import subprocess
        import tempfile
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        scripts = self._scripts(html)
        self.assertTrue(scripts, f"{label}: no inline script found")
        for i, js in enumerate(scripts):
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
                fh.write(js)
                path = fh.name
            try:
                r = subprocess.run([node, "--check", path],
                                   capture_output=True, text=True)
            finally:
                Path(path).unlink()
            self.assertEqual(r.returncode, 0,
                             f"{label} script {i} does not parse:\n{r.stderr}")

    def test_launcher_scripts_parse(self):
        from recordward import launcher
        self._check("launcher (first run)", launcher._launcher_html(True))
        self._check("launcher (ready)", launcher._launcher_html(False))

    def test_dashboard_scripts_parse(self):
        import recordward.core as core
        src = {"name": "X", "url": "", "notes": "", "every_days": 30}
        st = [core.status_for(src, [])]
        self._check("dashboard (live)", core.render_page(st, interactive=True,
                                                          script_nonce="n"))
        self._check("dashboard (static)", core.render_page(st))


class TestPrefsReminderChoices(unittest.TestCase):
    """Preferences only offers reminder choices where they can be scheduled."""

    def _html(self, supported):
        from unittest import mock
        from recordward import launcher
        st = {"preference": "off", "supported": supported, "installed": False,
              "active": False, "setup_complete": True}
        with mock.patch.object(launcher, "reminder_status", return_value=st):
            return launcher._launcher_html(False)

    def test_unsupported_system_shows_note_not_choices(self):
        html = self._html(False)
        self.assertNotIn('name="pcad"', html)
        self.assertNotIn("recordward reminders set", html)
        self.assertIn('id="no-reminders"', html)

    def test_supported_system_offers_choices(self):
        html = self._html(True)
        self.assertIn('name="pcad" value="weekly"', html)
        self.assertNotIn('id="no-reminders"', html)
