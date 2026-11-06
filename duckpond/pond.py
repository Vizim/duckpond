"""duckpond pond: a btop-style heads-up display of the agents running right now."""
import math
import os
import unicodedata
import re
import shutil
import sys
import time

from . import config, sessions
from .duck import BOLD, DIM, MINI_ROWS, RESET

ANSI = re.compile(r'\x1b\[[0-9;]*m')
CYAN, GREEN, YELLOW = '\033[36m', '\033[38;5;41m', '\033[33m'
WAVE = '⠈⠉⠁⠀⠀⢀⣀⡀⠀⠀'
SPIN = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
EYE = '⠄'
DUCKLING = ['⢀⠀⣰⣻⠦', '⠘⢿⣿⡿⠃']
BUBBLE_TICKS = 14
BOXES = ('pond', 'tokens', 'context', 'totals')
SUPER = '⁰¹²³⁴⁵⁶⁷⁸⁹'
CTX_TIERS = {'claude': (200_000, 1_000_000), 'codex': (272_000, 400_000, 1_000_000),
             'copilot': (128_000, 200_000, 1_000_000), 'vscode': (128_000, 200_000, 1_000_000)}
CTX_DEFAULT = (128_000, 200_000, 400_000, 1_000_000)
CARD_MIN, CARD_MAX = 28, 56
PKG = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')
TICK = 0.25


to_epoch = sessions.to_epoch


def ago(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f'{seconds}s'
    if seconds < 3600:
        return f'{seconds // 60}m'
    if seconds < 86400:
        m = seconds % 3600 // 60
        return f'{seconds // 3600}h' + (f' {m}m' if m else '')
    return f'{seconds // 86400}d'


def human(n):
    n = float(n or 0)
    for unit, size in (('M', 1e6), ('k', 1e3)):
        if n >= size:
            v = n / size
            return f'{v:.1f}{unit}' if v < 10 else f'{v:.0f}{unit}'
    return f'{int(n)}'


def tilde(path):
    path = path or ''
    return '~' + path[len(HOME):] if path.startswith(HOME) else path


def live_ducks():
    live = sessions.live_claude()
    hidden = set(sessions.load_json(sessions.HIDDEN, []))
    rows, _ = sessions.session_rows([], live, hidden)
    out = []
    for mtime, agent, sid, where, d, status in rows:
        if not status:
            continue
        lock = live.get(sid, {}) if agent == 'claude' else {}
        out.append(dict(agent=agent, sid=sid, title=sessions.title(d), status=status, root=where,
                        branch=d['branch'], turns=d['turns'], cost=d['cost'], last=mtime, tool=d.get('tool'),
                        ducklings=[v[0] for v in (d.get('subagents') or {}).values()
                                   if time.time() - v[1] < 3600][:4],
                        since=to_epoch(lock.get('since')) or mtime,
                        started=to_epoch(lock.get('started')) or to_epoch(d['started']),
                        tin=sum(m[1] for m in d.get('tok') or ()), tout=sum(m[2] for m in d.get('tok') or ()),
                        recent=[m for m in (d.get('tok') or ())[-30:]],
                        cached=sum(m[3] if len(m) > 3 else 0 for m in d.get('tok') or ()), ctx=d.get('ctx') or 0,
                        ctx_limit=d.get('ctx_limit') or 0,
                        prompt=d['prompts'][-1] if d['prompts'] else '', reply=d['reply'] or ''))
    return out


def demo_ducks():
    now = time.time()
    return [
        dict(agent='claude', sid='a', title='Rate limiter returns 429 too early', status='busy', root='~/code/api',
             branch='fix/limiter', turns=34, cost=4.2, last=now - 3, since=now - 12, started=now - 4300,
             prompt='the burst window is still off by one, check the token refill math', reply='',
             tool='Bash run the limiter tests', ducklings=['explore the auth module', 'review the diff'],
             tin=4_100_000, tout=61_000, cached=3_850_000, ctx=168_000),
        dict(agent='codex', sid='b', title='redis cache for pricing', status='busy', root='~/code/pricing',
             branch='main', turns=9, cost=None, last=now - 40, since=now - 95, started=now - 1500,
             prompt='add a 60s ttl and a cache miss counter', reply='', tool='shell pytest tests/test_cache.py', ducklings=[],
             tin=380_000, tout=9_800, cached=210_000, ctx=42_000),
        dict(agent='hermes', sid='c', title='Reconcile October statements', status='idle', root='~/finance',
             branch=None, turns=12, cost=0.8, last=now - 600, since=now - 600, started=now - 7200,
             prompt='flag anything over $500 that has no receipt', reply='Three transactions flagged.', ducklings=[],
             tin=52_000, tout=4_100, cached=0, ctx=0),
    ]


def water(width, t, phase=0):
    return ''.join(WAVE[(i + t + phase) % len(WAVE)] for i in range(width))


def status_tag(duck, t):
    s = duck['status']
    age = ago(time.time() - duck['since'])
    if s == 'busy':
        return f'{GREEN}{SPIN[t % len(SPIN)]} busy{RESET} {DIM}{age}{RESET}'
    return f'{DIM}· {s} {age}{RESET}'


def card(duck, width, t, compact=False):
    # What the session is doing, in a column under its duck. Compact keeps the first four lines.
    color = sessions.AGENTS.get(duck['agent'], {}).get('color', '')
    facts = []
    if duck['started']:
        facts.append(f"up {ago(time.time() - duck['started'])}")
    if duck['turns']:
        facts.append(f"{duck['turns']} prompt{'s' if duck['turns'] != 1 else ''}")
    if isinstance(duck['cost'], (int, float)):
        facts.append(f"${duck['cost']:.2f}")
    if duck.get('tin'):
        facts.append(f"{int(round(100 * (duck.get('cached') or 0) / duck['tin']))}% cached")
    busy_s, span_s = duck.get('worked') or (0.0, 0.0)
    share = f"  {DIM}worked {ago(busy_s)}/{ago(span_s)}{RESET}" if span_s >= 60 else ''
    lines = [f"{color}{duck['agent']}{RESET} {status_tag(duck, t)}{share}",
             f"{BOLD}{sessions.one_line(duck['title'], width)}{RESET}",
             f"{DIM}{sessions.one_line(' '.join(filter(None, [tilde(duck['root']), duck['branch']])), width)}{RESET}",
             f"{DIM}{sessions.one_line(' · '.join(facts), width)}{RESET}"]
    rin, rout = duck.get('rate') or (0, 0)
    lines.append(f"{DIM}tok{RESET} {human(duck.get('tin'))} in · {human(duck.get('tout'))} out"
                 f"  {DIM}▼{RESET}{human(rin)}/s {DIM}▲{RESET}{human(rout * 60)}/m"
                 + (f"  {DIM}ctx{RESET} {human(duck['ctx'])}" if duck.get('ctx') else ''))
    if compact:
        lines = [lines[0], lines[1], lines[4]]
        if duck['status'] == 'busy' and duck.get('tool'):
            name, _, rest = duck['tool'].partition(' ')
            lines.append(f"{YELLOW}⚙ {name}{RESET} {DIM}{sessions.one_line(rest, max(4, width - len(name) - 3))}{RESET}")
        return [clip(line, width) for line in lines]
    if duck.get('ducklings'):
        n = len(duck['ducklings'])
        lines.append(f"{DIM}{n} duckling{'s' if n != 1 else ''}{RESET} "
                     f"{DIM}{sessions.one_line(', '.join(duck['ducklings']), max(4, width - 12))}{RESET}")
    if duck['status'] == 'busy' and duck.get('tool'):
        name, _, rest = duck['tool'].partition(' ')
        lines.append(f"{YELLOW}⚙ {name}{RESET} {DIM}{sessions.one_line(rest, max(4, width - len(name) - 3))}{RESET}")
    if duck['prompt']:
        words, first, second = duck['prompt'].split(), '', ''
        while words and len(first) + len(words[0]) + 1 <= width - 2:
            first = (first + ' ' + words.pop(0)).strip()
        second = ' '.join(words)
        lines.append(f"{DIM}›{RESET} {first}")
        if second:
            lines.append('  ' + sessions.one_line(second, width - 2))
    return [clip(line, width) for line in lines]


def paint(cells, colors):
    text, current = '', ''
    for ch, color in zip(cells, colors):
        if color != current:
            text += color or RESET
            current = color
        text += ch
    return (text + (RESET if current else '')).rstrip()


def flip(ch):
    # Mirror one Braille cell: left column dots swap with right column dots.
    b = ord(ch) - 0x2800
    if not 0 <= b < 256:
        return ch
    m = ((b & 0x07) << 3) | ((b & 0x38) >> 3) | ((b & 0x40) << 1) | ((b & 0x80) >> 1)
    return chr(0x2800 + m)


def mirror(rows):
    return [''.join(flip(c) for c in reversed(row)) for row in rows]


def wander(t, k, span, busy):
    # Paddle back and forth across the slot; busy ducks cover it faster. Returns offset and heading.
    period = 32 + 8 * (k % 3) if busy else 72 + 16 * (k % 3)
    phase = (t + k * 19) % period
    half = period // 2
    pos = phase if phase < half else period - phase
    return round((pos / half - 0.5) * 2 * span), (1 if phase < half else -1)


def pose(duck, t, k):
    # The art for this tick: blink now and then, face the way it is paddling, hop when idle.
    busy = duck['status'] == 'busy'
    art = list(MINI_ROWS)
    if (t + k * 7) % 23 == 0:
        art = [row.replace(EYE, '\u2800') for row in art]
    if duck.get('heading', 1) < 0:
        art = mirror(art)
    if busy:
        bob = (t // 2 + k) % 2
    else:
        bob = 0 if (t + k * 11) % 44 < 2 else 1
    return art, bob


def bubble_text(duck, t, k):
    if duck.get('bubble') and t - duck['bubble'][1] < BUBBLE_TICKS:
        return duck['bubble'][0]
    if duck['status'] != 'busy' and (t + k * 29) % 160 < 5:
        return 'quack'
    return ''


def pond_row(ducks, width, t, offset, compact=False, extra_water=0):
    # One row of ducks: a bubble line, the art, two rows of water with ripples, then the cards.
    slot = width // len(ducks)
    duck_w = len(MINI_ROWS[0])
    card_w = min(slot - 2, CARD_MAX)
    height = len(MINI_ROWS) + 2
    rows = [[' '] * width for _ in range(height)]
    colors = [[''] * width for _ in range(height)]
    waves = [list(water(width, t)), list(water(width, t, 3))]
    cards = []
    for i, duck in enumerate(ducks):
        k = offset + i
        busy = duck['status'] == 'busy'
        trail = 6 * len(duck.get('ducklings') or ()) + 3 if duck.get('ducklings') else 0
        span = max(0, min(slot, card_w + 2) // 2 - duck_w // 2 - 1 - trail // 2)
        dx, heading = wander(t, k, span, busy)
        duck['heading'] = heading
        art, bob = pose(duck, t, k)
        x = i * slot + min(slot, card_w + 2) // 2 - duck_w // 2 + dx + heading * (trail // 2)
        x = max(0, min(x, width - duck_w))
        color = sessions.AGENTS.get(duck['agent'], {}).get('color', '')
        for r, part in enumerate(art):
            for j, ch in enumerate(part):
                if ch != '\u2800':
                    rows[r + 1 + bob][x + j] = ch
                    colors[r + 1 + bob][x + j] = color
        for j in range(len(duck.get('ducklings') or ())):
            # Ducklings paddle in a line behind the parent, moving and bobbing with it.
            gap = 2 + 6 * j
            dx0 = x - len(DUCKLING[0]) - gap if heading > 0 else x + duck_w + gap
            lo, hi = i * slot, min(width, (i + 1) * slot) - len(DUCKLING[0])
            if not lo <= dx0 <= hi:
                continue
            art2 = DUCKLING if heading > 0 else mirror(DUCKLING)
            dbob = bob
            for r, part in enumerate(art2):
                for jj, ch in enumerate(part):
                    if ch != '\u2800':
                        rows[r + 3 + dbob][dx0 + jj] = ch
                        colors[r + 3 + dbob][dx0 + jj] = color
        text = bubble_text(duck, t, k)
        if text:
            bx = max(0, min(x + duck_w // 2 - len(text) // 2, width - len(text)))
            for j, ch in enumerate(text):
                rows[0][bx + j] = ch
                colors[0][bx + j] = GREEN if text != 'quack' else DIM
        if busy:
            ring = (t + k) % 4
            for px in (x - 1 - ring, x + duck_w + ring):
                if 0 <= px < width:
                    waves[0][px] = '⠒'
        elif heading:
            px = x - 1 if heading > 0 else x + duck_w
            if 0 <= px < width and (t + k) % 6 < 3:
                waves[0][px] = '⠂'
        cards.append(card(duck, card_w, t, compact) if slot >= CARD_MIN else
                     [f"{color}{duck['agent']}{RESET} {status_tag(duck, t)}",
                      sessions.one_line(duck['title'], max(8, slot - 2))])
    out = [paint(row, row_colors) for row, row_colors in zip(rows, colors)]
    out += [f'{CYAN}{"".join(w)}{RESET}' for w in waves]
    out += [f'{CYAN}{water(width, t, 6 + 3 * n)}{RESET}' for n in range(extra_water)]
    for n in range(max(len(c) for c in cards)):
        line = ''
        for i, c in enumerate(cards):
            cell = c[n] if n < len(c) else ''
            line += cell + ' ' * max(0, slot - cells(cell))
        out.append(line.rstrip())
    return out


def frame(ducks, width, t, compact=False, sky=0, extra_water=0):
    # sky adds empty rows above the ducks and extra_water adds water rows below, to fill a taller box.
    width = max(48, width)
    if not ducks:
        sign = f'{DIM}no sessions running right now. start an agent and come back.{RESET}'
        return [''] * sky + ['', '', ' ' * ((width - 58) // 2) + sign, '', f'{CYAN}{water(width, t)}{RESET}',
                f'{CYAN}{water(width, t, 3)}{RESET}', f'{CYAN}{water(width, t, 6)}{RESET}'] + [
                    f'{CYAN}{water(width, t, 9 + 3 * n)}{RESET}' for n in range(extra_water)] + ['']
    per_row = max(1, min(len(ducks), width // CARD_MIN))
    out = [''] * sky
    for start in range(0, len(ducks), per_row):
        out += ([] if compact else ['']) + pond_row(ducks[start:start + per_row], width, t, start, compact, extra_water)
    return out


def header(ducks, width):
    n = len(ducks)
    busy = sum(1 for d in ducks if d['status'] == 'busy')
    parts = [f'{BOLD}duckpond{RESET}', f'{DIM}{n} session{"s" if n != 1 else ""} running{RESET}']
    if n:
        parts.append(f'{GREEN}{busy} busy{RESET} {DIM}{n - busy} idle{RESET}')
    left = '  '.join(parts)
    width = max(20, width)
    clock = time.strftime('%H:%M:%S')
    pad = max(1, width - cells(left) - len(clock))
    return left + ' ' * pad + f'{DIM}{clock}{RESET}'




LEFT_DOTS, RIGHT_DOTS = (0x40, 0x04, 0x02, 0x01), (0x80, 0x20, 0x10, 0x08)
GRADIENT = ('\033[38;5;41m', '\033[38;5;78m', '\033[38;5;114m', '\033[38;5;150m', '\033[38;5;186m',
            '\033[38;5;222m', '\033[38;5;215m', '\033[38;5;208m')
BORDER = '\033[38;5;240m'
GRADIENT_OUT = ('\033[38;5;33m', '\033[38;5;39m', '\033[38;5;45m', '\033[38;5;51m', '\033[38;5;87m',
                '\033[38;5;123m', '\033[38;5;159m', '\033[38;5;195m')
BLOCKS = ' ▁▂▃▄▅▆▇█'
VFLIP = {0x01: 0x40, 0x40: 0x01, 0x02: 0x04, 0x04: 0x02, 0x08: 0x80, 0x80: 0x08, 0x10: 0x20, 0x20: 0x10}


def stretch(values, n):
    # Resample a short series so each value becomes a block of columns.
    values = list(values) or [0]
    return [values[min(len(values) - 1, i * len(values) // n)] for i in range(n)]


def scaled(values, log=False):
    # Normalise to 0..1; log compresses the bursts so small replies still show.
    if log:
        values = [math.log1p(max(0.0, v)) for v in values]
    top = max(values) if values else 0
    return [v / top for v in values] if top else [0.0 for _ in values]


def vflip(line):
    # Turn a graph row upside down, for the "out" half of a network-style graph.
    out = ''
    for ch in line:
        b = ord(ch) - 0x2800
        if 0 <= b < 256:
            b = sum(VFLIP[bit] for bit in VFLIP if b & bit)
            ch = chr(0x2800 + b)
        out += ch
    return out


def braille_graph(values, width, rows, palette=GRADIENT):
    # btop-style graph: two samples per cell, four dot levels per row, coloured bottom to top.
    samples = width * 2
    values = ([0.0] * samples + list(values))[-samples:]
    levels = [min(rows * 4, round(max(0.0, min(1.0, v)) * rows * 4)) for v in values]
    out = []
    for r in range(rows):
        base = (rows - 1 - r) * 4
        line = ''
        for c in range(width):
            cell = 0
            for dots, lvl in ((LEFT_DOTS, levels[2 * c]), (RIGHT_DOTS, levels[2 * c + 1])):
                for k in range(4):
                    if lvl > base + k:
                        cell |= dots[k]
            line += chr(0x2800 + cell)
        shade = palette[min(len(palette) - 1, (rows - 1 - r) * len(palette) // max(1, rows))]
        out.append(f'{shade}{line}{RESET}')
    return out


def meter(label, share, width, color):
    # label [■■■■■□□□□□] 47%
    cells = max(4, width - len(label) - 8)
    filled = round(max(0.0, min(1.0, share)) * cells)
    return f'{label} {BORDER}[{RESET}{color}{"■" * filled}{RESET}{DIM}{"□" * (cells - filled)}{RESET}{BORDER}]{RESET}{int(round(share * 100)):>4}%'


def cells(text):
    # Terminal columns a string takes: wide glyphs count two, combining marks none, colour codes nothing.
    n = 0
    for ch in ANSI.sub('', text):
        if unicodedata.combining(ch):
            continue
        n += 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
    return n


def clip(line, width):
    # Cut a coloured line at a visible width without breaking the colour codes; ends in an ellipsis when cut.
    if cells(line) <= width:
        return line
    out, seen, target = '', 0, max(0, width - 1)
    for part in re.split(r'(\x1b\[[0-9;]*m)', line):
        if part.startswith('\x1b'):
            out += part
            continue
        for ch in part:
            w = cells(ch)
            if seen + w > target:
                return out + RESET + ('…' if width else '')
            out += ch
            seen += w
    return out + RESET + ('…' if width else '')


def box(title, lines, width, height=None, right='', num=0):
    # btop's frame: rounded corners, the title hung in the top edge as ┐¹title┌, facts at the top right.
    inner = width - 2
    title = title[:max(0, inner - 4)]
    label = f'{BORDER}┐{RESET}{BOLD}{YELLOW}{SUPER[num] if num else ""}{GREEN}{title}{RESET}{BORDER}┌'
    used = len(title) + 3 + (1 if num else 0)
    if right and inner - used - len(right) - 2 < 2:
        right = ''
    gap = max(0, inner - used - (len(right) + 2 if right else 0))
    top = (f'{BORDER}╭─' + label + '─' * gap
           + (f' {RESET}{DIM}{right}{RESET}{BORDER} ' if right else '') + f'╮{RESET}')
    if height:
        lines = (list(lines) + [''] * height)[:height - 2]
    body = []
    for line in lines:
        line = clip(line, inner - 2)
        pad = max(0, inner - 2 - cells(line))
        body.append(f'{BORDER}│{RESET} {line}{" " * pad} {BORDER}│{RESET}')
    return [top] + body + [f'{BORDER}╰' + '─' * inner + f'╯{RESET}']


def beside(*columns):
    return [''.join(col[i] if i < len(col) else ' ' * cells(col[0]) for col in columns)
            for i in range(max(len(c) for c in columns))]


def stats(entries, now=None):
    # Totals for today and all time, per agent, plus prompts per hour over the last day.
    now = now or time.time()
    lt = time.localtime(now)
    midnight = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    st = dict(sessions=0, prompts=0, cost=0.0, today=0, prompts_today=0, cost_today=0.0, tin=0, tout=0,
              tin_today=0, tout_today=0, cached=0, cached_today=0, active_hours=set(), agents={}, hours=[0] * 24)
    for e in entries:
        d = e['data']
        if not d.get('root') or (d['turns'] == 0 and not d['custom'] and not d['ai']):
            continue
        cost = d['cost'] if isinstance(d['cost'], (int, float)) else 0.0
        st['sessions'] += 1
        st['prompts'] += d['turns']
        st['cost'] += cost
        a = st['agents'].setdefault(e['agent'], dict(sessions=0, prompts=0, cost=0.0, tout=0))
        a['sessions'] += 1
        a['prompts'] += d['turns']
        a['cost'] += cost
        for m in d.get('tok') or ():
            minute, tin, tout = m[:3]
            cached = m[3] if len(m) > 3 else 0
            st['tin'] += tin
            st['tout'] += tout
            st['cached'] += cached
            a['tout'] += tout
            if minute >= midnight:
                st['tin_today'] += tin
                st['tout_today'] += tout
                st['cached_today'] += cached
                st['active_hours'].add(int(minute // 3600))
        if e['mtime'] >= midnight:
            st['today'] += 1
            st['cost_today'] += cost
        for ts in d.get('times') or ():
            if ts >= midnight:
                st['prompts_today'] += 1
            age = now - ts
            if 0 <= age < 86400:
                st['hours'][23 - int(age // 3600)] += 1
    return st


def money(v):
    return f'${v:,.2f}'


def totals_lines(st, width, net=None):
    wide = width >= 56
    cols = ('sessions', 'prompts', 'tok in', 'tok out', 'cost') if wide else ('sessions', 'prompts', 'cost')
    rows = [f"{DIM}{'':<9}" + ''.join(f'{c:>9}' for c in cols) + RESET]
    for label, key in (('today', 'today'), ('all time', 'all')):
        if key == 'today':
            vals = [st['today'], st['prompts_today'], human(st['tin_today']), human(st['tout_today']), money(st['cost_today'])]
        else:
            vals = [st['sessions'], st['prompts'], human(st['tin']), human(st['tout']), money(st['cost'])]
        if not wide:
            vals = [vals[0], vals[1], vals[4]]
        rows.append(f'{label:<9}' + ''.join(f'{v:>9}' for v in vals))
    rows.append('')
    mw = min(width, 44)
    hit = st['cached_today'] / st['tin_today'] if st['tin_today'] else (st['cached'] / st['tin'] if st['tin'] else 0.0)
    rows.append(meter('cache hit', hit, mw, GREEN))
    rows.append(f'{DIM}tokens out by agent{RESET}')
    total = max(1, st['tout'])
    for agent in sessions.AGENTS:
        a = st['agents'].get(agent)
        if a:
            rows.append(meter(f'{agent:<9}', a['tout'] / total, mw, sessions.AGENTS[agent]['color']))
    hours = max(1, len(st.get('active_hours') or ()))
    rows.append(f"{DIM}today{RESET} {money(st['cost_today'] / hours)}/h · {st['prompts_today'] / hours:.0f} prompts/h "
                f"· {human(st['tout_today'] / hours)} out/h {DIM}· {hours}h active{RESET}")
    hours = st.get('hours') or [0] * 24
    peak = max(hours) or 1
    strip = ''.join(BLOCKS[min(8, round(h / peak * 8))] if h else BLOCKS[0] for h in hours)
    rows += ['', f'{DIM}24h{RESET} {GREEN}{strip}{RESET} {DIM}{sum(hours)} prompts · peak {peak}/h{RESET}']
    return rows


def worked(seen, now):
    # Seconds a session was busy out of the seconds observed, from timestamped samples.
    if len(seen) < 2:
        return (0.0, 0.0)
    busy = sum(b - a for (a, flag), (b, _) in zip(seen, seen[1:]) if flag)
    return (busy, now - seen[0][0])


class Sampler:
    """Live rates over a sliding window: tokens in per second, tokens out, and spend, per session and overall."""

    WINDOW = 60.0
    WORKED_WINDOW = 600.0

    def __init__(self):
        self.started = None
        self.ducks = []
        self.prev = {}
        self.hist = {}
        self.busy_per = {}
        self.tin, self.tout, self.busy, self.burn, self.ctx = [], [], [], [], []
        self.rate_in = self.rate_out = 0.0
        self.interval = 1.0

    def seed(self, ducks, now):
        # First sample: rebuild the last few minutes from the index's per-minute buckets so the
        # graph and rates do not start from nothing every time the pond opens.
        samples = 400
        self.tin, self.tout = [0.0] * samples, [0.0] * samples
        for duck in ducks:
            last_in = last_out = 0
            for minute, tin, tout, *_ in duck.get('recent') or ():
                for i in range(samples):
                    at = now - (samples - 1 - i) * self.interval
                    if minute <= at < minute + 60:
                        self.tin[i] += tin / 60.0
                        self.tout[i] += tout / 60.0
                if minute + 60 > now - self.WINDOW:
                    last_in += tin
                    last_out += tout
            if last_in or last_out:
                self.hist[duck['sid']] = [(now, last_in, last_out, 0.0)]
        self.ctx = [float(sum(d.get('ctx') or 0 for d in ducks))] * samples
        self.started = now - self.WINDOW

    def sample(self, ducks, now=None):
        now = now or time.time()
        if self.started is None:
            self.seed(ducks, now)
        self.ducks = list(ducks)
        span = max(1.0, min(self.WINDOW, now - self.started))
        total_in = total_out = spend = 0.0
        for duck in ducks:
            sid = duck['sid']
            fresh = duck['tin']
            cost = duck['cost'] if isinstance(duck.get('cost'), (int, float)) else 0.0
            prev = self.prev.get(sid)
            hist = self.hist.setdefault(sid, [])
            if prev:
                hist.append((now, max(0, fresh - prev[0]), max(0, duck['tout'] - prev[1]), max(0.0, cost - prev[2])))
            elif hist:
                hist[-1] = (now, hist[-1][1], hist[-1][2], hist[-1][3])
            while hist and now - hist[0][0] > self.WINDOW:
                hist.pop(0)
            rin = sum(h[1] for h in hist) / span
            rout = sum(h[2] for h in hist) / span
            burn = sum(h[3] for h in hist) / span * 3600
            seen = self.busy_per.setdefault(sid, [])
            seen.append((now, duck['status'] == 'busy'))
            while seen and now - seen[0][0] > self.WORKED_WINDOW:
                seen.pop(0)
            duck['rate'] = (rin, rout)
            duck['worked'] = worked(seen, now)
            self.prev[sid] = (fresh, duck['tout'], cost)
            total_in += rin
            total_out += rout
            spend += burn
        for sid in list(self.prev):
            if sid not in {d['sid'] for d in ducks}:
                del self.prev[sid]
                self.hist.pop(sid, None)
                self.busy_per.pop(sid, None)
        self.rate_in, self.rate_out = total_in, total_out
        self.tin.append(total_in)
        self.tout.append(total_out)
        self.burn.append(spend)
        self.ctx.append(float(sum(d.get('ctx') or 0 for d in ducks)))
        self.busy.append(busy_share(ducks))
        for series in (self.tin, self.tout, self.busy, self.burn, self.ctx):
            del series[:-400]
        return self


def ducks_for_meters(net):
    return sorted(net.ducks, key=lambda d: -(d.get('ctx') or 0))[:6]


def ctx_limit(ctx, agent='claude'):
    # The context window a session is running in: the smallest size for that agent it still fits.
    tiers = CTX_TIERS.get(agent, CTX_DEFAULT)
    return next((lim for lim in tiers if ctx <= lim), tiers[-1])


def lower(st, net, width, height, hidden=()):
    # The btop part: a network-style tokens graph (in up, out down), the spend graph, and totals with meters.
    show = [b for b in BOXES[1:] if b not in hidden]
    if height < 5 or not show:
        return []
    if width < 100:
        show = show[-1:]
    totals_w = (66 if width >= 160 else 40) if 'totals' in show else 0
    if len(show) == 1:
        totals_w = width if show == ['totals'] else 0
    graphs = [b for b in show if b != 'totals']
    left_w = (width - totals_w) * 3 // 5 if len(graphs) == 2 else (width - totals_w if graphs else 0)
    mid_w = width - totals_w - left_w if len(graphs) == 2 else (width - totals_w if 'context' in graphs and 'tokens' not in graphs else 0)
    graph_h = height - 3
    top_h = graph_h // 2
    gw = max(2, left_w - 4)
    up = braille_graph(scaled(net.tin[-gw * 2:], log=True), gw, top_h)
    divider = clip(f'{GREEN}▼ in{RESET}{BORDER}' + '─' * max(0, gw - 11) + f'{RESET}{CYAN}▲ out{RESET}', gw)
    down = [vflip(line) for line in reversed(braille_graph(scaled(net.tout[-gw * 2:], log=True), gw, max(1, graph_h - top_h - 1), GRADIENT_OUT))]
    axis = (f'{GREEN}▼ in{RESET} {human(net.rate_in)}/s   {CYAN}▲ out{RESET} {human(net.rate_out * 60)}/m'
            f'   {DIM}log scale · 1 min averages · last {gw * 2 * net.interval:g}s{RESET}')
    tokens = box('tokens', up + [divider] + down + [axis], left_w, height, num=2,
                 right=f"today {human(st['tin_today'])} in · {human(st['tout_today'])} out")
    bw = max(2, mid_w - 4)
    meters = []
    for d in ducks_for_meters(net):
        ctx, lim = d.get('ctx') or 0, d.get('ctx_limit') or ctx_limit(d.get('ctx') or 0, d['agent'])
        tail = f"{human(ctx):>5}/{human(lim)}" if bw >= 34 else f"{human(ctx):>5}"
        meters.append(meter(f"{sessions.one_line(d['title'], 10):<10}", ctx / lim, bw - len(tail) - 2,
                            sessions.AGENTS[d['agent']]['color']) + f' {DIM}{tail}{RESET}')
    rows_for_graph = max(1, graph_h - len(meters))
    total_ctx = net.ctx[-1] if net.ctx else 0
    total_lim = sum(d.get('ctx_limit') or ctx_limit(d.get('ctx') or 0, d['agent']) for d in net.ducks) or 1
    context = box('context', braille_graph([v / total_lim for v in net.ctx[-bw * 2:]], bw, rows_for_graph, GRADIENT) + meters
                  + [f'{DIM}{human(total_ctx)} of {human(total_lim)} across the pond{RESET}'],
                  mid_w, height, num=3, right=f'last {bw * 2 * net.interval:g}s')
    totals = box('totals', totals_lines(st, totals_w - 4, net), totals_w, height, num=4)
    cols = {'tokens': tokens, 'context': context, 'totals': totals}
    return beside(*[cols[b] for b in show if (left_w if b == 'tokens' else mid_w if b == 'context' else totals_w) > 0])


def plain(lines):
    return [ANSI.sub('', line) for line in lines]


def source_stamp():
    out = {}
    for name in os.listdir(PKG):
        if name.endswith('.py'):
            try:
                st = os.stat(os.path.join(PKG, name))
                out[name] = (st.st_mtime_ns, st.st_size)
            except OSError:
                pass
    return out


def source_ok(stamp, now):
    # Compile the files that changed so a half-typed edit never takes the pond down.
    for name in now:
        if stamp.get(name) != now[name]:
            try:
                with open(os.path.join(PKG, name), encoding='utf-8') as fh:
                    compile(fh.read(), name, 'exec')
            except (SyntaxError, OSError, UnicodeDecodeError) as e:
                return f'{name}: {e}'
    return None


class Keys:
    """Single keypresses without echo; a no-op when stdin is not a terminal."""

    def __init__(self):
        self.fd = None
        self.saved = None

    def __enter__(self):
        if sys.platform != 'win32' and sys.stdin.isatty():
            import termios
            import tty
            self.fd = sys.stdin.fileno()
            self.saved = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def __exit__(self, *exc):
        if self.saved is not None:
            import termios
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)
            self.saved = None

    def read(self, timeout):
        if sys.platform == 'win32':
            import msvcrt
            end = time.time() + timeout
            while time.time() < end:
                if sys.stdin.isatty() and msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ('\x00', '\xe0'):
                        msvcrt.getwch()
                        return ''
                    return ch
                time.sleep(0.02)
            return ''
        if self.fd is None:
            time.sleep(timeout)
            return ''
        import select
        ready, _, _ = select.select([self.fd], [], [], timeout)
        return os.read(self.fd, 8).decode('utf-8', 'ignore') if ready else ''


def refresh(ducks, fresh, t):
    # Carry heading and bubbles over, and say something when a session changes state.
    by_sid = {d['sid']: d for d in ducks}
    for duck in fresh:
        old = by_sid.get(duck['sid'])
        if old is None:
            if ducks or t > 8:
                duck['bubble'] = ('hello!', t)
            continue
        duck['heading'] = old.get('heading', 1)
        duck['bubble'] = old.get('bubble')
        duck['rate'], duck['worked'] = old.get('rate'), old.get('worked')
        if old['status'] == 'busy' and duck['status'] != 'busy':
            duck['bubble'] = ('done!', t)
        elif old['status'] != 'busy' and duck['status'] == 'busy':
            duck['bubble'] = ('on it', t)
    return fresh


def busy_share(ducks):
    return sum(1 for d in ducks if d['status'] == 'busy') / len(ducks) if ducks else 0.0


def demo_stats():
    hours = [0, 0, 0, 0, 0, 0, 0, 1, 3, 6, 9, 7, 4, 2, 5, 8, 10, 6, 3, 1, 0, 0, 2, 4]
    return dict(sessions=61, prompts=1480, cost=212.4, today=7, prompts_today=71, cost_today=9.3,
                tin=212_000_000, tout=5_100_000, tin_today=12_400_000, tout_today=310_000,
                cached=190_000_000, cached_today=10_900_000, active_hours={9, 10, 11, 14, 15, 16},
                agents={'claude': dict(sessions=44, prompts=1200, cost=201.1, tout=3_900_000),
                        'codex': dict(sessions=12, prompts=220, cost=11.3, tout=900_000),
                        'hermes': dict(sessions=5, prompts=60, cost=0.0, tout=300_000)}, hours=hours)


def demo_net(ducks):
    net = Sampler()
    net.ducks = list(ducks)
    net.prev = {d['sid']: (0, 0, 0.0) for d in ducks}
    for i in range(120):
        wave = abs(((i * 3) % 40) - 20) / 20
        burst = 1.0 if 70 < i < 95 else 0.2
        net.tin.append(2800 * wave * burst + 150)
        net.tout.append(60 * (1 - wave) * burst + 4)
        net.busy.append(min(1.0, 0.33 + (0.34 if 30 < i < 50 or 70 < i < 95 else 0.0) + (0.33 if 40 < i < 46 else 0.0)))
        net.burn.append(18.0 * wave * burst + 2.5)
        net.ctx.append(60_000 + 110_000 * i / 120)
    for k, duck in enumerate(ducks):
        series = [max(0.0, 40 * abs((((i + 9 * k) * 5) % 16) - 8) / 8 - (0 if duck['status'] == 'busy' else 40)) for i in range(80)]
        duck['rate'] = (series[-1] * 60, series[-1])
        duck['worked'] = ((480.0, 600.0), (330.0, 600.0), (60.0, 600.0))[k % 3]
    net.rate_in, net.rate_out = net.tin[-1], net.tout[-1]
    return net


def demo_step(ducks, t):
    if t % 60 == 30:
        ducks[1]['status'] = 'idle' if ducks[1]['status'] == 'busy' else 'busy'
        ducks[1]['since'] = time.time()
        ducks[1]['bubble'] = ('done!' if ducks[1]['status'] == 'idle' else 'on it', t)
    return ducks


def screen(ducks, t, st, net, width, height, note=None, interval=1.0, hidden=()):
    # Header, the pond box with ducks and cards, the stats boxes, footer; sized to the terminal.
    lines = [header(ducks, width)]
    only_pond = all(b in hidden for b in BOXES[1:])
    if 'pond' not in hidden:
        pond = frame(ducks, width - 4, t)
        if len(pond) + 10 > height and not only_pond:
            pond = frame(ducks, width - 4, t, compact=True)
        spare = height - 2 - 1 - 2 - len(pond)
        if only_pond and spare > 0:
            # The pond alone gets the whole screen: more sky above the ducks and deeper water below.
            rows = len(ducks) and -(-len(ducks) // max(1, min(len(ducks), (width - 4) // CARD_MIN))) or 1
            extra = min(spare // 2 // rows, 6)
            pond = frame(ducks, width - 4, t, sky=spare - extra * rows, extra_water=extra)
        n = len(ducks)
        busy = sum(1 for d in ducks if d['status'] == 'busy')
        facts = f'{n} session{"s" if n != 1 else ""} · {busy} busy' if n else 'nothing running'
        lines += box('pond', pond, width, right=facts, num=1)
    lines += lower(st, net, width, height - len(lines) - 2, hidden)
    keys = ' '.join(f'{SUPER[i + 1]}{b}' if b not in hidden else f'{SUPER[i + 1]}{DIM}{b}{RESET}' for i, b in enumerate(BOXES))
    foot = (f'{DIM}q quit · r refresh · + - interval {interval:g}s · {RESET}{keys}'
            if not note else f'{YELLOW}{note}{RESET}')
    return lines[:max(3, height - 2)] + ['', foot]


def hidden_boxes():
    return {b.strip() for b in (config.get('pond_hidden') or '').split(',') if b.strip() in BOXES}


def draw(ducks, t, st, net, note=None, interval=1.0, hidden=()):
    # Redraw in place: home the cursor and pad every row, so nothing flickers or scrolls.
    size = shutil.get_terminal_size((80, 24))
    lines = screen(ducks, t, st, net, size.columns, size.lines, note, interval, hidden)
    lines = (lines + [''] * size.lines)[:size.lines]
    padded = [clip(line, size.columns) + ' ' * max(0, size.columns - cells(clip(line, size.columns))) for line in lines]
    sys.stdout.write('\033[H' + '\n'.join(padded))
    sys.stdout.flush()


def run(args):
    once, demo = '--once' in args, '--demo' in args
    interval = 1.0
    if '--interval' in args:
        try:
            interval = max(0.25, min(10.0, float(args[args.index('--interval') + 1])))
        except (IndexError, ValueError):
            sys.exit('usage: duckpond pond [--interval SECONDS] [--once] [--demo]')
    ducks = demo_ducks() if demo else live_ducks()
    st = demo_stats() if demo else stats(sessions.collect().values())
    net = demo_net(ducks) if demo else Sampler()
    net.interval = interval
    if not demo:
        net.sample(ducks)
    if once:
        size = shutil.get_terminal_size((80, 24))
        sys.stdout.write('\n'.join(screen(ducks, 0, st, net, size.columns, size.lines)[:-2]) + '\n')
        return
    stamp, note, t, due = source_stamp(), None, 0, time.time() + interval
    stats_due, hidden = time.time() + 10, hidden_boxes()
    sys.stdout.write('\033[?1049h\033[?25l\033[2J')
    try:
        with Keys() as keys:
            while True:
                draw(ducks, t, st, net, note, interval, hidden)
                key = keys.read(TICK)
                t += 1
                if key == '\x1b' or any(ch in 'qQ' for ch in key):
                    return
                for ch in key:
                    if ch in '+=':
                        interval = min(10.0, interval * 2)
                    elif ch in '-_':
                        interval = max(0.25, interval / 2)
                    elif ch in '1234':
                        name = BOXES[int(ch) - 1]
                        hidden ^= {name}
                        config.set_value('pond_hidden', ','.join(b for b in BOXES if b in hidden))
                        sys.stdout.write('\033[2J')
                if demo:
                    ducks = demo_step(ducks, t)
                elif any(ch in 'rR' for ch in key) or time.time() >= due:
                    due = time.time() + interval
                    net.interval = interval
                    ducks = refresh(ducks, live_ducks(), t)
                    net.sample(ducks)
                    if time.time() >= stats_due or any(ch in 'rR' for ch in key):
                        stats_due = time.time() + 10
                        st = stats(sessions.collect().values())
                if t % 2 == 0:
                    now = source_stamp()
                    if now != stamp:
                        note = source_ok(stamp, now)
                        if note is None:
                            raise RuntimeError('reload')
                        note = f'waiting on {note}'
    except KeyboardInterrupt:
        return
    except RuntimeError as e:
        if str(e) != 'reload':
            raise
        sys.stdout.write('\033[?25h\033[?1049l')
        sys.stdout.flush()
        argv = sys.argv if not sys.argv[0].endswith('cli.py') else ['-m', 'duckpond.cli'] + sys.argv[1:]
        os.execv(sys.executable, [sys.executable] + argv)
    finally:
        sys.stdout.write('\033[?25h\033[?1049l')
        sys.stdout.flush()
