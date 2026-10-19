# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: build Muse Video Studio (one-dir, không console).

Build trên Windows:
    pip install -r requirements.txt
    pyinstaller muse-video-studio.spec
Kết quả: dist/MuseVideoStudio/MuseVideoStudio.exe

BÀI HỌC v1.7.0: icon PHẢI là đường dẫn tuyệt đối (tính từ SPECPATH),
không dùng đường dẫn tương đối.
"""
import os

block_cipher = None

# Đường dẫn tuyệt đối tới icon — không bao giờ dùng relative path ở đây.
_ICON_ICO = os.path.join(SPECPATH, "app", "assets", "icon.ico")

a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=[],
    datas=[('HUONG-DAN.md', '.'),  # file hướng dẫn đọc trong app (menu ❓)
           ('app/assets', 'app/assets')],  # icon app + dấu tick checkbox
    hiddenimports=[
        'googleapiclient.discovery',
        'googleapiclient.http',
        'google.auth.transport.requests',
        'google.oauth2.credentials',
        'google_auth_oauthlib.flow',
        'keyring.backends.Windows',
    ],
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
    name='MuseVideoStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # TẮT UPX: nén DLL hay gây lỗi "Failed to start embedded
    # python interpreter" trên một số máy Windows
    console=False,  # App desktop thật: không hiện cửa sổ cmd.
    # Mọi lỗi đều xem được trong app (toolbar "Log hệ thống").
    icon=_ICON_ICO,  # tuyệt đối từ SPECPATH (bài học v1.7.0)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,  # BẮT BUỘC: chứa base_library.zip (PyInstaller 6.x đưa nó vào datas)
    a.zipfiles,
    a.zipped_data,
    strip=False,
    upx=False,  # xem ghi chú ở trên
    upx_exclude=[],
    name='MuseVideoStudio',
)
