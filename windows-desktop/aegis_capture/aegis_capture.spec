# -*- mode: python ; coding: utf-8 -*-
#
# BUG FIX vs. original: the original spec listed
# assets/mt5_color_match_guide.jpg, guides/mt5_color_match_guide.jpg,
# and mq5/AEGIS_Executor.mq5 unconditionally in `datas`. PyInstaller
# fails the ENTIRE build with a bare "file not found" if any single one
# of those is missing at build time. This version checks explicitly and
# fails fast with a clear message naming exactly which file is missing,
# instead of a build that fails deep inside PyInstaller's internals.
#
# If you'd rather the build succeed without these files (e.g. the color
# guide image genuinely isn't ready yet), change REQUIRE_ALL_ASSETS to
# False below.

import os

REQUIRE_ALL_ASSETS = True

_candidate_datas = [
    ('assets/mt5_color_match_guide.jpg', 'assets'),
    ('guides/mt5_color_match_guide.jpg', 'guides'),
    ('mq5/AEGIS_Executor.mq5', 'mq5'),
]

datas = []
missing = []
for src, dest in _candidate_datas:
    if os.path.exists(src):
        datas.append((src, dest))
    else:
        missing.append(src)

if missing:
    msg = "Missing expected data file(s) for AEGIS_Capture build: " + ", ".join(missing)
    if REQUIRE_ALL_ASSETS:
        raise SystemExit(
            f"\n\n*** BUILD FAILED: {msg} ***\n"
            "These paths are relative to the repo root where PyInstaller is invoked.\n"
            "Either add the missing file(s), or set REQUIRE_ALL_ASSETS = False in "
            "aegis_capture.spec to build without them (the in-app Color Guide button "
            "and/or the bundled EA file will then be unavailable at runtime).\n"
        )
    else:
        print(f"WARNING: {msg} — continuing build without them.")

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['mss', 'PIL', 'requests'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AEGIS_Capture',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)
