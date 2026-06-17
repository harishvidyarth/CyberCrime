# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the standalone FundTrail app (single local laptop, offline).
#
#   Build ON the target OS (PyInstaller CANNOT cross-compile):
#       Windows : build_exe.bat   -> dist\FundTrail.exe
#       Mac/Lin : ./build_exe.sh  -> dist/FundTrail
#
# The built binary is a git-ignored artifact (dist/, build/, *.exe) — only this spec
# and the build scripts are committed, so you rebuild after every feature update.

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

datas = [
    ('main/templates', 'templates'),
    ('main/static', 'static'),
    ('main/migrations', 'migrations'),
    ('main/IFSC_CODES.pkl', '.'),
    ('main/letter_template_suspect_accounts.docx', '.'),
    ('main/letter_template_victim_account.docx', '.'),
]
# Packages that ship data files PyInstaller misses unless asked.
for _pkg in ('xhtml2pdf', 'reportlab', 'docx', 'svglib', 'qrcode'):
    try:
        datas += collect_data_files(_pkg)
    except Exception:
        pass

hiddenimports = []
for _pkg in (
    'pandas', 'openpyxl', 'reportlab', 'xhtml2pdf', 'docx', 'svglib',
    'flask_sqlalchemy', 'flask_login', 'flask_wtf', 'flask_limiter',
    'flask_migrate', 'flask_compress', 'pyotp', 'qrcode', 'PIL', 'sqlalchemy',
    'webview',  # pywebview — standalone desktop window for the .exe
):
    try:
        hiddenimports += collect_submodules(_pkg)
    except Exception:
        pass

a = Analysis(
    ['run_exe.py'],
    pathex=['main'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FundTrail',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # keep a console so the officer sees the URL and any startup error
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
