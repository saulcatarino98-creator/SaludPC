# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from pathlib import Path

# Recopilar dependencias de pythonnet (.NET runtime)
tmp_ret = collect_all('pythonnet')
datas = tmp_ret[0]
binaries = tmp_ret[1]
hiddenimports = tmp_ret[2]

# Agregar DLLs de LibreHardwareMonitor y dependencias .NET desde empaquetado/sensores
sensores_dir = Path('empaquetado/sensores')
if sensores_dir.is_dir():
    for dll in sensores_dir.glob('*.dll'):
        binaries.append((str(dll), dll.name))

# También asegurar que el DLL principal esté como dato (para rutas.buscar_recurso)
datas.append(
    ('empaquetado/sensores/LibreHardwareMonitorLib.dll', 'LibreHardwareMonitorLib.dll')
)

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='app',
)
