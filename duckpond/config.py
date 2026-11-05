"""User settings in an ini file: ~/.config/duckpond/config.ini (or %APPDATA%\\duckpond on Windows)."""
import configparser
import os
import sys

KEYS = {
    'terminal': 'command that opens a new terminal window running the program given after it, e.g. "alacritty -e"',
}


def path():
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
    else:
        base = os.environ.get('XDG_CONFIG_HOME') or os.path.join(os.path.expanduser('~'), '.config')
    return os.path.join(base, 'duckpond', 'config.ini')


def load():
    cp = configparser.ConfigParser()
    cp.read(path(), encoding='utf-8')
    return dict(cp['duckpond']) if cp.has_section('duckpond') else {}


def get(key):
    # Environment wins over the file, so a one-off override is still possible.
    return os.environ.get(f'DUCKPOND_{key.upper()}') or os.environ.get(f'DUCKPOND_{key.upper()}') or load().get(key)


def set_value(key, value):
    if key not in KEYS:
        sys.exit(f'duckpond: unknown setting {key!r}, known: {", ".join(KEYS)}')
    cp = configparser.ConfigParser()
    cp.read(path(), encoding='utf-8')
    if not cp.has_section('duckpond'):
        cp.add_section('duckpond')
    if value:
        cp.set('duckpond', key, value)
    else:
        cp.remove_option('duckpond', key)
    os.makedirs(os.path.dirname(path()), exist_ok=True)
    with open(path(), 'w', encoding='utf-8') as fh:
        cp.write(fh)


def show():
    current = load()
    lines = [f'config file: {path()}']
    for key, help_text in KEYS.items():
        lines.append(f'  {key:<10} {current.get(key) or "(default)"}    {help_text}')
    lines.append('set one with: duckpond config terminal "alacritty -e"   (empty value resets it)')
    return '\n'.join(lines)
