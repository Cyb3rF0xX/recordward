# PyInstaller spec for RecordWard (spike). Build from the repo root:
#   pyinstaller --noconfirm packaging/recordward.spec
import sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
is_win = sys.platform.startswith("win")
is_mac = sys.platform == "darwin"

# pywebview picks its GUI backend at runtime, so list its platform modules.
hidden = collect_submodules("webview")

a = Analysis(
    ["entry.py"],
    pathex=[".."],
    datas=[("../recordward/assets", "recordward/assets")],
    hiddenimports=hidden,
    excludes=["tkinter", "_tkinter", "unittest", "pydoc", "test", "qtpy", "PyQt5", "PyQt6", "PySide2", "PySide6"],
    cipher=block_cipher,
)
# The GTK hook copies entire desktop icon themes and locales (~260 MB on
# Linux). The app draws its own UI in a web view and needs neither.
_DROP = ("share/icons", "share/locale", "share/themes")
a.datas = [d for d in a.datas if not d[0].replace("\\", "/").startswith(_DROP)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="RecordWard",
    console=False,            # GUI app: no console window on Windows/macOS
    icon="../recordward/assets/icon.ico" if is_win else None,
)
coll = COLLECT(exe, a.binaries, a.zipped_data, a.datas, name="RecordWard")
if is_mac:
    app = BUNDLE(
        coll,
        name="RecordWard.app",
        icon=None,  # TODO: generate icon.icns on macOS (iconutil) in CI
        bundle_identifier="com.cyb3rf0xx.recordward",
    )
