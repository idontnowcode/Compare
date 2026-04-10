# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=collect_dynamic_libs('PyQt6'),
    datas=[
        *collect_data_files('PyQt6'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtPrintSupport',
        'PyQt6.sip',
        'paramiko',
        'paramiko.transport',
        'paramiko.auth_handler',
        'paramiko.sftp_client',
        'paramiko.sftp_file',
        'paramiko.channel',
        'PIL',
        'PIL.Image',
        'PIL.ImageChops',
        'PIL.ImageEnhance',
        'cryptography',
        'bcrypt',
        'nacl',
        'difflib',
        'hashlib',
        'fnmatch',
        'json',
        'subprocess',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy'],
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
    name='Compare',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico',  # uncomment to set a custom icon
)
