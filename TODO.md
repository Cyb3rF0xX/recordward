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

- [ ] **App logo / icon.** The project has no logo or icon. Needs:
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

## Notes

- These are tracked here so they survive across sessions. When implemented,
  check the box and note the version in `CHANGELOG.md`.
