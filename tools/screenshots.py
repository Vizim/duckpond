"""Regenerate the README screenshots from generated sample data.

    python tools/screenshots.py

Writes docs/duck.svg, docs/pond.svg and docs/doctor.svg. Never reads real sessions.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, 'tests'))
import render_term  # noqa: E402
import sample_stores  # noqa: E402
from duckpond.duck import banner  # noqa: E402
from duckpond import picker  # noqa: E402


def run(env, *args):
    return subprocess.run([sys.executable, '-m', 'duckpond.cli', *args], capture_output=True, text=True,
                          env=env, cwd=REPO).stdout


ANSI = __import__('re').compile(r'\x1b\[[0-9;]*m')
GREEN, DIM, BOLD, RESET, SEL = '\x1b[32m', '\x1b[2m', '\x1b[1m', '\x1b[0m', '\x1b[1m'


def wrap(line, width):
    plain = ANSI.sub('', line)
    if len(plain) <= width:
        return [line]
    out, rest = [], line
    while len(ANSI.sub('', rest)) > width:
        plain = ANSI.sub('', rest)
        cut = plain.rfind(' ', 0, width)
        cut = cut if cut > 20 else width
        head = plain[:cut]
        idx = rest.find(head) + len(head)
        out.append(rest[:idx])
        rest = rest[idx:].lstrip()
    out.append(rest)
    return out


def clip(line, width):
    # Cut an ANSI-coloured line at a visible width, keeping the colour codes intact.
    out, seen, i = '', 0, 0
    for part in __import__('re').split(r'(\x1b\[[0-9;]*m)', line):
        if part.startswith('\x1b'):
            out += part
            continue
        room = width - seen
        if len(part) > room:
            out += part[:max(0, room - 1)] + '…'
            return out + RESET
        out += part
        seen += len(part)
    return out


def picker_screen(rows, preview_lines, query, selected, width=150, left=74):
    """Compose what fzf shows: rounded frame with the duckpond label, header, rows, and the preview pane."""
    right = width - left - 3
    top = f'{DIM}╭{RESET}{GREEN} duckpond {RESET}{DIM}' + '─' * (width - 12) + f'╮{RESET}'
    bottom = f'{DIM}╰' + '─' * (width - 2) + f'╯{RESET}'
    header = picker.header(rows).splitlines()
    left_lines = [f'{GREEN}sessions › {RESET}{query}{DIM}▌{RESET}'] + header + ['']
    for i, row in enumerate(rows):
        label = row.split('\t')[3]
        left_lines.append((f'{GREEN}▶{RESET} ' if i == selected else '  ') + clip(label, left - 3))
    right_lines = [w for line in preview_lines for w in wrap(line, right)]
    height = max(len(left_lines), len(right_lines))
    out = [top]
    for i in range(height):
        l = left_lines[i] if i < len(left_lines) else ''
        r = right_lines[i] if i < len(right_lines) else ''
        pad = ' ' * max(0, left - len(ANSI.sub('', l)))
        out.append(f'{DIM}│{RESET} ' + l + pad + f'{DIM}│{RESET} ' + r)
    out.append(bottom)
    return '\n'.join(out)


def main():
    tmp = tempfile.mkdtemp(prefix='duckpond-shots-')
    stores = os.path.join(tmp, 'stores')
    sample_stores.build(stores)
    shim = os.path.join(tmp, 'bin')
    os.makedirs(shim)
    for name in ('claude', 'codex', 'hermes', 'fzf'):
        path = os.path.join(shim, name)
        with open(path, 'w') as fh:
            fh.write('#!/bin/sh\necho 0.74.5\n')
        os.chmod(path, 0o755)
    env = dict(os.environ, CLAUDE_CONFIG_DIR=f'{stores}/claude', CODEX_HOME=f'{stores}/codex',
               HERMES_HOME=f'{stores}/hermes', DUCKPOND_CACHE=f'{tmp}/cache', HOME='/home/ada',
               PATH=shim + os.pathsep + os.environ['PATH'], COLUMNS='120', LINES='38')
    docs = os.path.join(REPO, 'docs')
    os.makedirs(docs, exist_ok=True)

    with open(os.path.join(tmp, 'duck.txt'), 'w', encoding='utf-8') as fh:
        fh.write(banner() + '\n')
    render_term.main(os.path.join(tmp, 'duck.txt'), os.path.join(docs, 'duck.svg'))

    rows = run(env, 'list').splitlines()
    sel = next(i for i, r in enumerate(rows) if not r.split('\t')[1].startswith('__'))
    agent, sid = rows[sel].split('\t')[:2]
    prev = run(env, 'preview', agent, sid).splitlines()
    with open(os.path.join(tmp, 'picker.txt'), 'w', encoding='utf-8') as fh:
        fh.write(picker_screen(rows, prev, '', sel) + '\n')
    render_term.main(os.path.join(tmp, 'picker.txt'), os.path.join(docs, 'picker.svg'))

    found = run(env, 'list', 'rocket').splitlines()
    agent, sid = found[0].split('\t')[:2]
    full = run(env, 'preview', '--full', agent, sid).splitlines()
    full = [('\x1b[1m' + l[2:] + '\x1b[0m') if l.startswith('# ') else l for l in full]
    full = [('\x1b[1m' + l.strip('*') + '\x1b[0m') if l.startswith('**') and l.endswith('**') else l for l in full]
    with open(os.path.join(tmp, 'search.txt'), 'w', encoding='utf-8') as fh:
        fh.write(picker_screen(found, full, 'rocket', 0) + '\n')
    render_term.main(os.path.join(tmp, 'search.txt'), os.path.join(docs, 'search.svg'))

    pond = run(env, 'pond', '--once', '--demo')
    with open(os.path.join(tmp, 'pond.txt'), 'w', encoding='utf-8') as fh:
        fh.write('\x1b[36m$\x1b[0m duckpond pond\n' + pond)
    render_term.main(os.path.join(tmp, 'pond.txt'), os.path.join(docs, 'pond.svg'))

    doctor = run(env, 'doctor')
    doctor = (doctor.replace(stores + '/', '/home/ada/.').replace(shim + '/', '/home/ada/.local/bin/')
              .replace(f'{tmp}/cache', '/home/ada/.cache/duckpond'))
    import platform
    doctor = doctor.replace(f'{platform.system()} {platform.release()}', 'Linux 6.17.0')
    with open(os.path.join(tmp, 'doctor.txt'), 'w', encoding='utf-8') as fh:
        fh.write('\x1b[36m$\x1b[0m duckpond doctor\n' + doctor)
    render_term.main(os.path.join(tmp, 'doctor.txt'), os.path.join(docs, 'doctor.svg'))
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
