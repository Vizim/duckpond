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


def run(env, *args):
    return subprocess.run([sys.executable, '-m', 'duckpond.cli', *args], capture_output=True, text=True,
                          env=env, cwd=REPO).stdout


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
               PATH=shim + os.pathsep + os.environ['PATH'], COLUMNS='120')
    docs = os.path.join(REPO, 'docs')
    os.makedirs(docs, exist_ok=True)

    with open(os.path.join(tmp, 'duck.txt'), 'w', encoding='utf-8') as fh:
        fh.write(banner() + '\n')
    render_term.main(os.path.join(tmp, 'duck.txt'), os.path.join(docs, 'duck.svg'))

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
