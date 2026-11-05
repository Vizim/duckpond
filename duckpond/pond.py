"""duckpond pond: the agents that are running right now, as ducks on a pond."""
import re
import shutil
import sys
import time

from . import sessions
from .duck import BOLD, DIM, MID_ROWS, MINI_ROWS, RESET

ANSI = re.compile(r'\x1b\[[0-9;]*m')
CYAN = '\033[36m'
WAVE = '⠈⠉⠁⠀⠀⢀⣀⡀⠀⠀'


def live_ducks():
    hidden = set(sessions.load_json(sessions.HIDDEN, []))
    rows, _ = sessions.session_rows([], sessions.live_claude(), hidden)
    return [(agent, sessions.title(d)) for _, agent, _, _, d, status in rows if status]


def water(width, t, phase=0):
    return ''.join(WAVE[(i + t + phase) % len(WAVE)] for i in range(width))


def frame(ducks, width, t):
    # Ducks bob on alternate ticks over three rows of drifting Braille water, labels underneath.
    width = max(48, width)
    if not ducks:
        sign = f'{DIM}no ducks on the pond right now. start an agent and come back.{RESET}'
        return ['', '', ' ' * ((width - 58) // 2) + sign, '', f'{CYAN}{water(width, t)}{RESET}',
                f'{CYAN}{water(width, t, 3)}{RESET}', f'{CYAN}{water(width, t, 6)}{RESET}', '']
    slot = max(len(MINI_ROWS[0]) + 4, width // len(ducks))
    art = MID_ROWS if slot >= len(MID_ROWS[0]) * 2 + 6 else MINI_ROWS
    duck_w = len(art[0])
    rows = [[' '] * width for _ in range(len(art) + 1)]
    colors = [[''] * width for _ in range(len(art) + 1)]
    labels = [[' '] * width for _ in range(2)]
    label_colors = [[''] * width for _ in range(2)]
    for i, (agent, title) in enumerate(ducks):
        x = min(i * slot + (slot - duck_w) // 2, width - duck_w)
        bob = (t + i) % 2
        color = sessions.AGENTS.get(agent, {}).get('color', '')
        for r, part in enumerate(art):
            for j, ch in enumerate(part):
                if ch != '\u2800':
                    rows[r + bob][x + j] = ch
                    colors[r + bob][x + j] = color
        for k, text in enumerate((agent, sessions.one_line(title, max(8, slot - 2)))):
            lx = max(0, min(x + duck_w // 2 - len(text) // 2, width - len(text)))
            for j, ch in enumerate(text):
                labels[k][lx + j] = ch
                label_colors[k][lx + j] = color if k == 0 else DIM
    out = ['']
    for row, row_colors in zip(rows + labels, colors + label_colors):
        text, current = '', ''
        for ch, color in zip(row, row_colors):
            if color != current:
                text += color or RESET
                current = color
            text += ch
        out.append((text + (RESET if current else '')).rstrip())
    out.insert(len(art) + 2, f'{CYAN}{water(width, t)}{RESET}')
    out.insert(len(art) + 3, f'{CYAN}{water(width, t, 3)}{RESET}')
    return out


def plain(lines):
    return [ANSI.sub('', line) for line in lines]


def run(args):
    once, demo = '--once' in args, '--demo' in args
    ducks = ([('claude', 'Rate limiter returns 429 too early'), ('codex', 'redis cache for pricing'),
              ('hermes', 'Reconcile October statements')] if demo else live_ducks())
    t = 0
    try:
        while True:
            width = shutil.get_terminal_size((80, 24)).columns
            lines = frame(ducks, width, t)
            n = len(ducks)
            header = f'{BOLD}duckpond{RESET}  {DIM}{n} duck{"s" if n != 1 else ""} on the pond{RESET}'
            if not once:
                sys.stdout.write('\033[H\033[2J')
            sys.stdout.write('\n'.join([header] + lines) + '\n')
            sys.stdout.flush()
            if once:
                return
            time.sleep(0.5)
            t += 1
            if t % 12 == 0 and not demo:
                ducks = live_ducks()
    except KeyboardInterrupt:
        sys.stdout.write('\n')
