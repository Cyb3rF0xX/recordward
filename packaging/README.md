# Packaging spike (PyInstaller)

Goal: one-download installs for non-technical users on Windows, macOS and
Linux, without rewriting the app. This is a **spike**: it records what was
tried and what is still unproven. The build workflow is `.github/workflows/build-bundles.yml`.

## Build locally (Linux/macOS)

```bash
python3 -m venv --system-site-packages .venv-pkg   # Linux: needs system GTK/gi
.venv-pkg/bin/pip install pyinstaller pywebview
cd packaging
../.venv-pkg/bin/pyinstaller --noconfirm --distpath ../dist \
    --workpath ../build/pyi recordward.spec
../dist/RecordWard/RecordWard            # opens the launcher window
../dist/RecordWard/RecordWard --version  # CLI arguments pass through
```

`entry.py` opens the native launcher when run with no arguments (double-click)
and passes arguments through otherwise.

## Results so far

### Local build (Fedora 44, Linux x86_64, Python 3.14)

| Check | Result |
|---|---|
| Build | Works, about 13 s |
| Launcher window from the bundle | Works: window, title-bar icon, layout OK |
| CLI passthrough (`--version`, `where`) | Works |
| Size | 348 MB at first. 80 MB (36 MB compressed) after dropping GTK icon themes/locales and tkinter/Qt |
| Runs on Ubuntu 24.04 (clean container) | **Fails**: `GLIBC_ABI_GNU2_TLS not found`. A binary built on Fedora 44 needs a newer glibc than most distros ship |
| WebKitGTK bundled | **No.** The Linux build still needs `WebKit2` typelib + `libwebkit2gtk` on the host |

### GitHub Actions builds (Python 3.12, run 43627218761, Nov 14 2026)

| Platform | Build + `--version` check | Artifact (compressed) |
|---|---|---|
| Windows (`windows-latest`) | Passes | 12 MB |
| macOS (`macos-latest`) | Passes | 52 MB |
| Linux (`ubuntu-22.04`) | Passes after pinning `PyGObject<3.51` (3.51+ needs girepository-2.0, missing on 22.04) | 57 MB |

The `--version` check only proves the program starts. No window has been opened from these builds yet.

### Hands-on tests

| Platform | Where | Result |
|---|---|---|
| Windows 11 Pro (build 26300) | Clean KVM/libvirt VM (UEFI, Secure Boot, TPM 2.0), local account, WebView2 152 | **Works** (Nov 14 2026, run 43646998315): launcher, title-bar/taskbar icon, Launch app, dashboard (3 columns), window controls, Preferences, clean Quit. Found and fixed: crash on start (PNG window icon; Windows needs `.ico`), spurious JS error after Launch app, needless launcher scrollbar, reminder choices shown where unsupported. SmartScreen not yet seen (disc copies have no download mark) |
| macOS | Needs a Mac | Not tested |
| Linux (clean distro) | Not yet | Not tested |

## Findings

1. **Linux binaries must be built on an old base** (for example Ubuntu 22.04 in
   CI) so they run on newer distros. Never ship a build made on a rolling or
   very new distro.
2. **The Linux bundle is not self-contained.** WebKitGTK is not included, so
   the user must have it (common on GNOME/KDE desktops, not guaranteed).
   Options: AppImage (bundle WebKitGTK, large), Flatpak (runtime provides it,
   best fit; Flathub listing), or document the package to install.
3. **Size** is dominated by GTK and Python. About 80 MB is acceptable; below
   that needs Tauri/Rust or a lighter toolkit.
4. **Signing is required for a smooth experience** on Windows (SmartScreen)
   and macOS (Gatekeeper + notarization). Not solved by any language choice.
5. **Windows** uses the Edge WebView2 runtime (present on current Windows 10/11)
   and `pythonnet`; **macOS** uses the built-in WKWebView.
6. The bundle is a GUI app (`console=False`). On Windows/macOS its CLI output
   is not shown; CLI users should keep using `pipx install git+https://github.com/Cyb3rF0xX/recordward`.

## Next steps

1. ~~Run the bundle workflow on GitHub Actions.~~ Done: all three build.
   Pushing a `vX.Y.Z` tag now also creates a DRAFT release with the
   bundles attached; review it, then publish it by hand.
2. Test each artifact (Windows: done, see above; macOS and a clean Linux still to do) on a clean machine or VM (no Python, no dev tools).
3. Decide Linux format (Flatpak vs AppImage) from what step 2 shows.
4. Generate `icon.icns` on macOS in CI (`iconutil`) and wire it into the spec.
5. Decide on signing (Apple developer account, Windows signing service).
6. Switch to Tauri/Rust only if these builds prove unreliable.
