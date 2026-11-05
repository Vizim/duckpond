"""aisp install-launcher: put an "AI Sessions" app with an icon where this desktop looks for apps."""
import os
import plistlib
import shutil
import subprocess
import sys

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
NAME = 'AI Sessions'
HOME = os.path.expanduser('~')


def aisp_exe():
    exe = shutil.which('aisp')
    if not exe:
        sys.exit('aisp: install the package first so the aisp command is on PATH')
    return os.path.abspath(exe)


def linux():
    exe = aisp_exe()
    share = os.environ.get('XDG_DATA_HOME') or os.path.join(HOME, '.local', 'share')
    for size in (16, 32, 48, 64, 128, 256, 512):
        d = os.path.join(share, 'icons', 'hicolor', f'{size}x{size}', 'apps')
        os.makedirs(d, exist_ok=True)
        shutil.copy(os.path.join(ASSETS, f'aisp-{size}.png'), os.path.join(d, 'aisp.png'))
    d = os.path.join(share, 'icons', 'hicolor', 'scalable', 'apps')
    os.makedirs(d, exist_ok=True)
    shutil.copy(os.path.join(ASSETS, 'aisp.svg'), os.path.join(d, 'aisp.svg'))
    apps = os.path.join(share, 'applications')
    os.makedirs(apps, exist_ok=True)
    path = os.path.join(apps, 'aisp.desktop')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('[Desktop Entry]\nType=Application\nName=AI Sessions\n'
                 'Comment=Pick and resume a recent Claude Code, Codex or Hermes session\n'
                 f'Exec={exe} --window\nIcon=aisp\nTerminal=false\nCategories=Development;\n'
                 'Keywords=claude;codex;hermes;sessions;agent;\n')
    for cmd in (['update-desktop-database', apps], ['gtk-update-icon-cache', '-q', os.path.join(share, 'icons', 'hicolor')]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f'installed {path}\nit should show up in your app menu as "{NAME}"; pin it from there'


def macos():
    exe = aisp_exe()
    app = os.path.join(HOME, 'Applications', f'{NAME}.app')
    macos_dir, res = os.path.join(app, 'Contents', 'MacOS'), os.path.join(app, 'Contents', 'Resources')
    os.makedirs(macos_dir, exist_ok=True)
    os.makedirs(res, exist_ok=True)
    runner = os.path.join(macos_dir, 'aisp-launcher')
    with open(runner, 'w', encoding='utf-8') as fh:
        fh.write(f'#!/bin/sh\nexec "{exe}" --window\n')
    os.chmod(runner, 0o755)
    shutil.copy(os.path.join(ASSETS, 'aisp.icns'), os.path.join(res, 'aisp.icns'))
    plist = dict(CFBundleName=NAME, CFBundleDisplayName=NAME, CFBundleIdentifier='dev.vizim.aisp',
                 CFBundleVersion='1', CFBundleShortVersionString='1.0', CFBundlePackageType='APPL',
                 CFBundleExecutable='aisp-launcher', CFBundleIconFile='aisp', LSMinimumSystemVersion='12.0')
    with open(os.path.join(app, 'Contents', 'Info.plist'), 'wb') as fh:
        plistlib.dump(plist, fh)
    os.utime(app)
    return f'installed {app}\ndrag it to the Dock, or open it from Launchpad or Spotlight'


def windows():
    exe = aisp_exe()
    start = os.path.join(os.environ.get('APPDATA', HOME), 'Microsoft', 'Windows', 'Start Menu', 'Programs')
    os.makedirs(start, exist_ok=True)
    lnk = os.path.join(start, f'{NAME}.lnk')
    icon = os.path.join(ASSETS, 'aisp.ico')
    script = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
              f"$s.TargetPath = '{exe}'; $s.Arguments = '--window'; $s.IconLocation = '{icon}';"
              f"$s.Description = 'Pick and resume a recent Claude Code, Codex or Hermes session'; $s.Save()")
    r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'aisp: could not create the shortcut: {r.stderr.strip()}')
    return f'installed {lnk}\nfind "{NAME}" in the Start menu and pin it to the taskbar from there'


def install():
    if sys.platform == 'darwin':
        return macos()
    if sys.platform == 'win32':
        return windows()
    return linux()
