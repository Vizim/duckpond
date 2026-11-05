"""duckpond pond: the agents that are running right now, as ducks on a pond."""
import re
import shutil
import sys
import time

from . import sessions

DUCK = ['  __    ', '<(o )___', ' ( ._> /', "  `---' "]
ANSI = re.compile(r'\x1b\[[0-9;]*m')
RESET = '\033[0m'


def live_ducks():
    hidden = set(sessions.load_json(sessions.HIDDEN, []))
    rows, _ = sessions.session_rows([], sessions.live_claude(), hidden)
    return [(agent, sessions.title(d)) for _, agent, _, _, d, status in rows if status]


def frame(ducks, width, t):
    # One picture: sky, a row of ducks bobbing on alternate ticks, two rows of water, labels.
    width = max(40, width)
    water = ''.join('~' if (i + t) % 4 < 2 else ' ' for i in range(width))
    if not ducks:
        sign = 'no ducks on the pond right now'
        return ['', '', sign.center(width).rstrip(), '', water, water, '']
    slot = max(10, width // len(ducks))
    chars = [[' '] * width for _ in range(5)]
    colors = [[''] * width for _ in range(5)]
    labels = [' '] * width
    for i, (agent, title) in enumerate(ducks):
        x = min(i * slot + (slot - 8) // 2, width - 8)
        bob = (t + i) % 2
        color = sessions.AGENTS.get(agent, {}).get('color', '')
        for r, part in enumerate(DUCK):
            for j, ch in enumerate(part):
                if ch != ' ':
                    chars[r + bob][x + j] = ch
                    colors[r + bob][x + j] = color
        label = sessions.one_line(title, max(6, slot - 2))
        lx = max(0, min(x + 4 - len(label) // 2, width - len(label)))
        for j, ch in enumerate(label):
            labels[lx + j] = ch
    out = ['']
    for row, row_colors in zip(chars, colors):
        text, current = '', ''
        for ch, color in zip(row, row_colors):
            if color != current:
                text += color or RESET
                current = color
            text += ch
        out.append((text + (RESET if current else '')).rstrip())
    out.append('\033[36m' + water + RESET)
    out.append('\033[36m' + water.replace('~', '-') + RESET)
    out.append(''.join(labels).rstrip())
    return out


def plain(lines):
    return [ANSI.sub('', line) for line in lines]


def run(args):
    once, demo = '--once' in args, '--demo' in args
    ducks = ([('claude', 'Rate limiter returns 429'), ('codex', 'redis cache'), ('hermes', 'Reconcile October')]
             if demo else live_ducks())
    t = 0
    try:
        while True:
            width = shutil.get_terminal_size((80, 24)).columns
            lines = frame(ducks, width, t)
            header = f'duckpond  {len(ducks)} duck{"s" if len(ducks) != 1 else ""} swimming'
            if not once:
                sys.stdout.write('\033[H\033[2J')
            sys.stdout.write('\n'.join([header] + lines) + '\n')
            sys.stdout.flush()
            if once:
                return
            time.sleep(0.6)
            t += 1
            if t % 10 == 0 and not demo:
                ducks = live_ducks()
    except KeyboardInterrupt:
        sys.stdout.write('\n')
