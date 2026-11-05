"""User settings in an ini file: ~/.config/aisp/config.ini (or %APPDATA%\\aisp on Windows)."""
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
    return os.path.join(base, 'aisp', 'config.ini')


def load():
    cp = configparser.ConfigParser()
    cp.read(path(), encoding='utf-8')
    return dict(cp['aisp']) if cp.has_section('aisp') else {}


def get(key):
    # Environment wins over the file, so a one-off override is still possible.
    return os.environ.get(f'AISP_{key.upper()}') or os.environ.get(f'AGENT_PICKER_{key.upper()}') or load().get(key)


def set_value(key, value):
    if key not in KEYS:
        sys.exit(f'aisp: unknown setting {key!r}, known: {", ".join(KEYS)}')
    cp = configparser.ConfigParser()
    cp.read(path(), encoding='utf-8')
    if not cp.has_section('aisp'):
        cp.add_section('aisp')
    if value:
        cp.set('aisp', key, value)
    else:
        cp.remove_option('aisp', key)
    os.makedirs(os.path.dirname(path()), exist_ok=True)
    with open(path(), 'w', encoding='utf-8') as fh:
        cp.write(fh)


def show():
    current = load()
    lines = [f'config file: {path()}']
    for key, help_text in KEYS.items():
        lines.append(f'  {key:<10} {current.get(key) or "(default)"}    {help_text}')
    lines.append('set one with: aisp config terminal "alacritty -e"   (empty value resets it)')
    return '\n'.join(lines)
