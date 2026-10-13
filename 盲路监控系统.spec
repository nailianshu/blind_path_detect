# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

block_cipher = None

# 获取项目根目录(spec文件所在目录)
project_root = Path(os.getcwd())

# 收集所有数据文件
datas = [
    (str(project_root / 'model'), 'model'),
    (str(project_root / 'icons'), 'icons'),
    (str(project_root / 'templates'), 'templates'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['ultralytics', 'cv2', 'PyQt5', 'numpy', 'flask', 'pyttsx3'],
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
    [],
    exclude_binaries=True,
    name='盲路监控系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='盲路监控系统',
)

app = BUNDLE(
    coll,
    name='盲路监控系统.app',
    icon=None,
    bundle_identifier='com.blindpath.monitor',
    info_plist={
        'NSCameraUsageDescription': '此应用需要访问摄像头以进行盲道检测',
    },
)