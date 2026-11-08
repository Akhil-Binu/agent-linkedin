# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [
    ('config/config.yaml', 'config'),
    ('config/content_bank.yaml', 'config'),
]
datas += collect_data_files('playwright')
datas += collect_data_files('reportlab')

hiddenimports = [
    'menu',
    'config.settings',
    'connectors.mock_linkedin',
    'connectors.playwright_linkedin',
    'connectors.linkedin_client',
    'core.analytics',
    'core.anti_slop',
    'core.carousel_generator',
    'core.content_bank',
    'core.evaluator',
    'core.generator',
    'core.hitl',
    'core.rate_limiter',
    'core.scheduler',
    'web.server',
    'playwright.sync_api',
    'reportlab.pdfgen.canvas',
    'reportlab.lib.colors',
    'reportlab.lib.pagesizes',
]

hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('fastapi')
hiddenimports += collect_submodules('starlette')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
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
    a.binaries,
    a.datas,
    [],
    name='linkedbot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
