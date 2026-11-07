
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH)
SITE_PACKAGES = ROOT / "venv-build" / "Lib" / "site-packages"

# Collect pyzkfp files and dependencies
zkfp_datas, zkfp_binaries, zkfp_hiddenimports = collect_all("pyzkfp")

# Collect Python.NET and CLR loader files
pythonnet_datas, pythonnet_binaries, pythonnet_hiddenimports = collect_all("pythonnet")
clr_datas, clr_binaries, clr_hiddenimports = collect_all("clr_loader")

datas = (
    zkfp_datas
    + pythonnet_datas
    + clr_datas
)

binaries = (
    zkfp_binaries
    + pythonnet_binaries
    + clr_binaries
)

# Ensure the ZKTeco .NET DLL is available at pyzkfp/dll
zkfp_dll = SITE_PACKAGES / "pyzkfp" / "dll" / "libzkfpcsharp.dll"

if not zkfp_dll.exists():
    raise FileNotFoundError(f"ZKTeco DLL not found: {zkfp_dll}")

binaries.append((str(zkfp_dll), "pyzkfp/dll"))

hiddenimports = list(set(
    zkfp_hiddenimports
    + pythonnet_hiddenimports
    + clr_hiddenimports
    + [
        "clr",
        "pythonnet",
        "clr_loader",
        "clr_loader.util.find_libpython",
        "PIL",
        "PIL.Image",
    ]
))

a = Analysis(
    ["agent.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ScannerAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    icon="fingerprint.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ScannerAgent",
)
