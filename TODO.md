# TODO / Backlog

Known work items, roughly prioritized. Not yet implemented.

## UI / UX

- [ ] **Card reflow on window resize.** Dashboard card elements don't reflow
  cleanly as the window/screen size changes. The grid uses
  `repeat(auto-fill, minmax(min(100%, 300px), 1fr))` with `clamp()` padding,
  but cards still don't flow correctly at some sizes (especially mid-range and
  when the native window is resized live). Fix so cards reflow smoothly from a
  narrow window up to full screen — verify in the pywebview window, the browser
  `serve` mode, and the static dashboard.

- [x] **App logo / icon.** (done in 1.1.0) The project has no logo or icon. Needs:
  - an app icon for the desktop launcher (`recordward.desktop` currently uses
    the generic `system-software-update`/stock icon) and the pywebview window;
  - a favicon / header mark for the dashboard UI;
  - ideally a single source (SVG) that scales to the various required sizes
    (16–512px, plus `.ico`/`.png` for packaging). On-theme with the dark UI
    and the "guard your own file" idea.

- [ ] **Default window size.** Set an appropriate default size (and sensible
  min size) for the native launcher/app window so the dashboard has room to
  show cards without immediately needing a resize. Current launcher window is
  480x580 with a 380x480 minimum — revisit once card reflow is fixed, since
  the right default depends on how cards lay out.

- [ ] **Design mockups (SVG).** Produce updated SVG mockups showing how the app
  *should* look — the dashboard and the native launcher/first-run window — as
  reference for the UI work above (card reflow, default window size, theming).
  These are design artifacts, separate from the app icon/logo item. Keep them
  in a `design/` or `docs/mockups/` folder and link them from the README.

- [ ] **Theme settings (Light / Dark / color).** Add a user-selectable theme:
  at minimum Light and Dark, ideally a custom accent color. Feasibility note:
  the dashboard already themes entirely through CSS custom properties
  (`--bg`, `--panel`, `--text`, `--muted`, `--line`, `--accent`, `--due`,
  `--ok`), so this is mostly (a) defining a light palette for those vars,
  (b) a `theme` setting (`dark` default / `light` / maybe `system`) persisted
  in `settings.json`, and (c) a toggle in the Settings panel + the launcher.
  Respect `prefers-color-scheme` for the `system` option. Make sure the chosen
  theme applies to both the dashboard and the launcher window.

## Distribution
- [ ] **One-download installs for Windows, macOS and Linux** (non-technical
  users). Spike in `packaging/` (see `packaging/README.md`): GitHub Actions
  builds Windows, macOS and Linux bundles. Hands-on testing: Windows 11
  works (VM); macOS and a clean Linux not yet. Windows/macOS have no
  automatic reminders yet (systemd only); Task Scheduler / launchd later.
- [ ] **Code signing.** Plan (Nov 2026): ship unsigned with SHA256SUMS for
  now. Next, apply to SignPath Foundation (free for OSI-licensed open source;
  AGPLv3 qualifies) for Windows signing in the bundle workflow. Check its
  terms first against any future paid/closed edition (it requires no
  proprietary components). macOS: Apple Developer Program ($99/yr, includes
  notarization) after the macOS bundle has been tested on a real Mac.
  Fallback for Windows: Azure Artifact Signing (~$9.99/mo; individual
  eligibility unclear). Open: Linux
  bundle needs system WebKitGTK (Flatpak/AppImage?), macOS `.icns`, and
  signing/notarization. Decide Python bundle vs Tauri/Rust after testing.

## Notes

- These are tracked here so they survive across sessions. When implemented,
  check the box and note the version in `CHANGELOG.md`.
