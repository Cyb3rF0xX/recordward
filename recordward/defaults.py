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
#   every_days  how often YOU want to be reminded (edit freely).
#   min_days    the shortest interval the provider allows for a FREE request.
#               The dashboard warns if every_days is lower than this, because
#               an earlier request may be refused or charged. 0 = no known limit.
#
# Basis: FCRA section 612(a) gives one free file disclosure per 12 months from
# each nationwide credit bureau and nationwide specialty agency (365). The three
# credit bureaus also offer free weekly reports through AnnualCreditReport.com
# (a voluntary program, made permanent in 2023), so their limit is 7.
# Provider policies change; check the card's links if a request is refused.

sources:
  # --- Credit bureaus via the only federally authorized free site ---
  - name: "Equifax (AnnualCreditReport)"
    url: "https://www.annualcreditreport.com"
    every_days: 30
    min_days: 7
    notes: "Free weekly report. Review Inquiries; freeze, fraud alert and disputes are free."

  - name: "Experian (AnnualCreditReport)"
    url: "https://www.annualcreditreport.com"
    every_days: 30
    min_days: 7
    notes: "Free weekly report. Review Inquiries; freeze, fraud alert and disputes are free."

  - name: "TransUnion (AnnualCreditReport)"
    url: "https://www.annualcreditreport.com"
    every_days: 30
    min_days: 7
    notes: "Free weekly report. Review Inquiries; freeze, fraud alert and disputes are free."

  # --- Specialty bureau that backs a lot of screening data ---
  - name: "LexisNexis Consumer Disclosure Report"
    url: "https://consumer.risk.lexisnexis.com/request"
    every_days: 365
    min_days: 365
    notes: "One free disclosure per 12 months. Freeze is free; opt-out form available."

  # --- Employment screening companies (request your own file + recipients) ---
  - name: "Checkr (file + 2yr recipients)"
    url: "https://candidate.checkr.com"
    every_days: 365
    min_days: 365
    notes: "One free file disclosure per 12 months. Disputes are free (portal)."

  - name: "Sterling (file request)"
    url: "https://www.consumerfinance.gov/consumer-tools/credit-reports-and-scores/consumer-reporting-companies/companies-list/sterling-talent-solutions/"
    every_days: 365
    min_days: 365
    notes: "One free file disclosure per 12 months. Contact details are on the CFPB listing."

  - name: "HireRight (file request)"
    url: "https://www.hireright.com/legal/consumer-rights"
    every_days: 365
    min_days: 365
    notes: "One free file disclosure per 12 months (includes DAC reports). Disputes are free."

  - name: "First Advantage (file request)"
    url: "https://fadv.com/candidates/free-report/"
    every_days: 365
    min_days: 365
    notes: "One free copy per year. Disputes: 800-845-6004."

  - name: "Accurate Background (file request)"
    url: "https://www.accurate.com/my-background-check/"
    every_days: 365
    min_days: 365
    notes: "One free file disclosure per 12 months. Disputes are free (online form)."

  # --- Catch-all: the CFPB list of consumer reporting companies ---
  - name: "CFPB list of consumer reporting companies"
    url: "https://www.consumerfinance.gov/consumer-tools/credit-reports-and-scores/consumer-reporting-companies/"
    every_days: 365
    min_days: 0
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
