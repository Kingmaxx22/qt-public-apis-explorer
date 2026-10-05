# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Qt Public APIs Explorer.

Builds a windowed (no console) onedir bundle:

    pyinstaller QtPublicApis.spec --noconfirm

`--onedir` is the default because a PySide6 onefile bundle unpacks ~200 MB to
a temp directory on every launch, which makes start-up feel broken. Pass
`--onefile` on the command line if a single portable file is required.
"""

import os

block_cipher = None

# Qt modules the app never touches. Dropping them roughly halves the bundle.
EXCLUDED_QT = [
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
    "PySide6.QtBluetooth", "PySide6.QtCharts", "PySide6.QtConcurrent",
    "PySide6.QtDataVisualization", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtHttpServer", "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets", "PySide6.QtNetworkAuth", "PySide6.QtNfc",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtPdf",
    "PySide6.QtPdfWidgets", "PySide6.QtPositioning", "PySide6.QtQml",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSensors",
    "PySide6.QtSerialBus", "PySide6.QtSerialPort", "PySide6.QtSpatialAudio",
    "PySide6.QtSql", "PySide6.QtStateMachine", "PySide6.QtSvgWidgets",
    "PySide6.QtTest", "PySide6.QtTextToSpeech", "PySide6.QtUiTools",
    "PySide6.QtVirtualKeyboard", "PySide6.QtWebChannel", "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets", "PySide6.QtXml",
    "tkinter", "unittest", "pydoc_data", "test",
]

ROOT = os.path.abspath(os.getcwd())
FONTS = os.path.join(ROOT, "assets", "fonts")
ICON = os.path.join(ROOT, "assets", "app.ico")
LICENSE = os.path.join(ROOT, "LICENSE")

datas = [
    (os.path.join(ROOT, "data", "catalog.json"), "data"),
]
if os.path.isfile(LICENSE):
    datas.append((LICENSE, "."))
if os.path.isdir(FONTS):
    for name in os.listdir(FONTS):
        datas.append((os.path.join(FONTS, name), os.path.join("assets", "fonts")))

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDED_QT,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="QtPublicAPIs",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # windowed: no console, like pythonw
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON if os.path.exists(ICON) else None,
    version="version_info.txt" if os.path.exists(
        os.path.join(ROOT, "version_info.txt")) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="QtPublicAPIs",
)