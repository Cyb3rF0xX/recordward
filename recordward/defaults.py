# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Cyb3rF0xX
"""Canonical default schedule, used for a fresh install and for 'reset'.

Kept as text (not a file) so it ships inside the installed package and is
always available even when the user's config dir is empty or wiped.
"""

from __future__ import annotations

DEFAULT_SCHEDULE_YAML = """\
# recordward schedule (US / FCRA)
#
# Each entry is a source you request your records from on a rotation.
# `every_days` is how often that source is due. The checker compares this
# against the last time you logged a request (in requests.log) and tells
# you what's due now.
#
# Edit freely: change cadences, add/remove sources, fix URLs if a vendor
# changes their consumer-disclosure page.

sources:
  # --- Credit bureaus via the only federally authorized free site ---
  - name: "Equifax (AnnualCreditReport)"
    url: "https://www.annualcreditreport.com"
    every_days: 30
    notes: "Pull full report; review the Inquiries section."

  - name: "Experian (AnnualCreditReport)"
    url: "https://www.annualcreditreport.com"
    every_days: 30
    notes: "Pull full report; review the Inquiries section."

  - name: "TransUnion (AnnualCreditReport)"
    url: "https://www.annualcreditreport.com"
    every_days: 30
    notes: "Pull full report; review the Inquiries section."

  # --- Specialty bureau that backs a lot of screening data ---
  - name: "LexisNexis Consumer Disclosure Report"
    url: "https://consumer.risk.lexisnexis.com/request"
    every_days: 90
    notes: "Free FCRA disclosure. Consider also placing a security freeze."

  # --- Employment screening companies (request your own file + recipients) ---
  - name: "Checkr (file + 2yr recipients)"
    url: "https://candidate.checkr.com"
    every_days: 180
    notes: "Request file disclosure + recipient list."

  - name: "Sterling (file request)"
    url: "https://www.sterlingcheck.com/contact/"
    every_days: 180
    notes: "Request file disclosure + recipient list."

  - name: "HireRight (file request)"
    url: "https://www.hireright.com/legal/consumer-rights"
    every_days: 180
    notes: "Request file disclosure + recipient list."

  - name: "First Advantage (file request)"
    url: "https://fadv.com/solutions/background-screening/consumer-center/"
    every_days: 180
    notes: "Request file disclosure + recipient list."

  - name: "Accurate Background (file request)"
    url: "https://www.accurate.com/consumer/"
    every_days: 180
    notes: "Request file disclosure + recipient list."

  # --- Catch-all: the CFPB list of consumer reporting companies ---
  - name: "CFPB list of consumer reporting companies"
    url: "https://www.consumerfinance.gov/consumer-tools/credit-reports-and-scores/consumer-reporting-companies/"
    every_days: 365
    notes: "Scan for any new specialty/employment screener to add above."
"""


DEFAULT_SETTINGS = {
    "port": 8765,
    "open_browser": True,
    "default_snooze_days": 30,
    "notify": True,
    # First-run / reminders (ADR-008)
    "setup_complete": False,          # has the user been through first-run setup?
    "reminders": "off",               # "off" | "weekly" | "monthly"
    "idle_shutdown_minutes": 15,      # server auto-exits after this idle gap (0 = never)
}
