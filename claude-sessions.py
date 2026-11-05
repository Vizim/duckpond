#!/usr/bin/env python3
"""List Claude Code sessions for the fzf picker and write a preview file per session."""
import glob
import json
import os
import re
import sys
import time

CACHE = os.environ.get('CLAUDE_PICKER_CACHE') or os.path.join(
    os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache')), 'claude-picker')
INDEX = os.path.join(CACHE, 'index.json')
HIDDEN = os.path.join(CACHE, 'hidden.json')
INDEX_VERSION = 2
SESSIONS = os.path.expanduser('~/.claude/projects/*/*.jsonl')
LIVE = os.path.expanduser('~/.claude/sessions/*.json')
KEEP_PROMPTS = 40
BOLD, DIM, GREEN, RESET = '\033[1m', '\033[2m', '\033[32m', '\033[0m'
CWD_RE = re.compile(r'"cwd":"([^"]*)"')
META_RE = re.compile(r'^\{"type":"([a-z-]+)"')
KEEP_TYPES = {'user', 'assistant', 'custom-title', 'ai-title', 'cost-state'}
SHELL_CD_RE = re.compile(r'<bash-input>\s*cd\b')
NOISE_CMDS = re.compile(r'/(compact|clear|exit|quit|model|help|cost|status|resume|usage|login|config|permissions|rename)\b')


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return '\n'.join(p.get('text', '') for p in content
                         if isinstance(p, dict) and p.get('type') == 'text')
    return ''


def real_prompt(d, text):
    # Skip injected context, shell echoes and interruptions; keep what the user typed.
    if d.get('isMeta') or d.get('isCompactSummary'):
        return None
    t = text.strip()
    m = re.search(r'<command-name>(/\S+)</command-name>', t)
    if m:
        t = m.group(1)
    if not t or t.startswith('<') or t.startswith('[Request interrupted'):
        return None
    if NOISE_CMDS.match(t):
        return None
    return t


def store_name(path):
    # Claude Code names a project's transcript folder after its path, one dash per other char.
    return re.sub(r'[^A-Za-z0-9-]', '-', path)


def new_state():
    return dict(root=None, shell=None, branch=None, custom=None, ai=None, prompts=[],
                reply=None, turns=0, cost=None, started=None)


def feed(s, line, store):
    # root: the project directory. shell: where the user last typed !cd.
    m = CWD_RE.search(line)
    if m:
        cwd = m.group(1)
        if not s['root'] or (store_name(cwd) == store and store_name(s['root']) != store):
            s['root'] = cwd
    m = META_RE.match(line)
    if m:
        if m.group(1) not in KEEP_TYPES:
            return
    elif '"type":"user"' in line:
        pass
    elif '"type":"assistant"' in line and '"type":"text"' in line:
        pass
    else:
        return
    try:
        d = json.loads(line)
    except ValueError:
        return
    if d.get('isSidechain'):
        return
    t = d.get('type')
    if t == 'user':
        s['branch'] = d.get('gitBranch') or s['branch']
        s['started'] = s['started'] or d.get('timestamp')
        text = text_of((d.get('message') or {}).get('content'))
        if SHELL_CD_RE.search(text) and d.get('cwd'):
            s['shell'] = d['cwd']
        p = real_prompt(d, text)
        if p:
            s['turns'] += 1
            s['prompts'].append(' '.join(p.split())[:300])
            s['prompts'] = s['prompts'][:1] + s['prompts'][1:][-KEEP_PROMPTS:]
    elif t == 'assistant':
        r = text_of((d.get('message') or {}).get('content')).strip()
        if r:
            s['reply'] = r[:1200]
    elif t == 'custom-title':
        s['custom'] = d.get('customTitle')
    elif t == 'ai-title':
        s['ai'] = d.get('aiTitle')
    elif t == 'cost-state':
        s['cost'] = d.get('totalCostUSD')


def scan(path, s, pos):
    # Transcripts are append-only, so resume from the last fully read line.
    store = os.path.basename(os.path.dirname(path))
    with open(path, 'rb') as fh:
        fh.seek(pos)
        for raw in fh:
            if not raw.endswith(b'\n'):
                break
            pos += len(raw)
            feed(s, raw.decode('utf-8', 'ignore'), store)
    return s, pos


def load_index():
    try:
        with open(INDEX) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_index(index):
    os.makedirs(CACHE, exist_ok=True)
    tmp = INDEX + '.tmp'
    with open(tmp, 'w') as fh:
        json.dump(index, fh)
    os.replace(tmp, INDEX)


def collect():
    old, new = load_index(), {}
    for path in glob.glob(SESSIONS):
        try:
            st = os.stat(path)
        except OSError:
            continue
        key = [st.st_mtime, st.st_size]
        hit = old.get(path)
        if hit and hit.get('v') == INDEX_VERSION and hit['key'] == key:
            new[path] = hit
            continue
        if hit and hit.get('v') == INDEX_VERSION and hit['pos'] <= st.st_size:
            state, pos = hit['data'], hit['pos']
        else:
            state, pos = new_state(), 0
        try:
            data, pos = scan(path, state, pos)
        except OSError:
            continue
        new[path] = dict(v=INDEX_VERSION, key=key, pos=pos, data=data)
        save_index({**old, **new})
    if new.keys() != old.keys():
        save_index(new)
    return new


def proc_start(pid):
    try:
        with open(f'/proc/{int(pid)}/stat') as fh:
            return fh.read().rsplit(')', 1)[1].split()[19]
    except (OSError, IndexError, TypeError, ValueError):
        return None


def live_sessions():
    # A pid alone is not proof: match the process start time the lock file recorded.
    out = {}
    for f in glob.glob(LIVE):
        try:
            with open(f) as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        start = proc_start(d.get('pid'))
        if not d.get('sessionId') or start is None:
            continue
        if d.get('procStart') is not None and str(d['procStart']) != start:
            continue
        out[d['sessionId']] = dict(status=d.get('status') or 'open', cwd=d.get('cwd'))
    return out


def one_line(s, n):
    s = ' '.join((s or '').split())
    return s if len(s) <= n else s[:n - 1] + '…'


def clip(s, n):
    s = (s or '').strip()
    return s if len(s) <= n else s[:n].rstrip() + ' …'


def title(d):
    first = d['prompts'][0] if d['prompts'] else ''
    return d['custom'] or d['ai'] or one_line(first, 70) or '(untitled)'


def when_str(ts):
    return time.strftime('%a %b %d %H:%M', time.localtime(ts))


def preview(sid, d, where, mtime, live):
    cost = f"${d['cost']:.2f}" if d['cost'] is not None else '-'
    started = '-'
    if d['started']:
        try:
            started = time.strftime('%b %d', time.strptime(d['started'][:10], '%Y-%m-%d'))
        except ValueError:
            pass
    out = [f"{BOLD}{title(d)}{RESET}"]
    if live:
        out.append(f"{GREEN}● already open in another window ({live['status']}){RESET}")
    out += [
        '',
        f"{DIM}resumes in{RESET} {where}",
        f"{DIM}project{RESET}    {d['root']}",
        f"{DIM}branch{RESET}     {d['branch'] or '-'}",
        f"{DIM}active{RESET}     {started} to {when_str(mtime)}",
        f"{DIM}prompts{RESET}    {d['turns']}    {DIM}cost{RESET} {cost}    {DIM}id{RESET} {sid[:8]}",
        '',
        f"{BOLD}WHAT YOU ASKED{RESET}",
    ]
    prompts = d['prompts']
    shown = prompts if len(prompts) <= 10 else prompts[:1] + ['…'] + prompts[-8:]
    for p in shown:
        out.append('  ' + p if p == '…' else f"  {DIM}·{RESET} {one_line(p, 220)}")
    if not prompts:
        out.append('  -')
    out += ['', f"{BOLD}LAST REPLY{RESET}", clip(d['reply'], 900) or '-']
    return '\n'.join(out) + '\n'


def matches(terms, d, where):
    h = ' '.join([title(d), where, d['root'] or '', d['branch'] or ''] + d['prompts'] + [d['reply'] or '']).lower()
    return all(t in h for t in terms)


def write_cached(name, text):
    path = os.path.join(CACHE, name + '.txt')
    try:
        with open(path) as fh:
            if fh.read() == text:
                return
    except OSError:
        pass
    with open(path, 'w') as fh:
        fh.write(text)


def prune_previews(keep):
    for f in glob.glob(os.path.join(CACHE, '*.txt')):
        if os.path.basename(f)[:-4] not in keep:
            try:
                os.remove(f)
            except OSError:
                pass


def load_hidden():
    try:
        with open(HIDDEN) as fh:
            return set(json.load(fh))
    except (OSError, ValueError):
        return set()


def save_hidden(hidden):
    os.makedirs(CACHE, exist_ok=True)
    with open(HIDDEN, 'w') as fh:
        json.dump(sorted(hidden), fh)


def main():
    args = sys.argv[1:]
    if args[:1] == ['--hide'] and len(args) == 2:
        save_hidden(load_hidden() | {args[1]})
        return
    if args == ['--unhide-all']:
        save_hidden(set())
        return
    # Every keystroke in the picker re-runs this with the query; all terms must appear.
    terms = ' '.join(args).lower().split()
    live = live_sessions()
    hidden = load_hidden()
    rows, known = [], {'__NEW__', '__CLOUD__'}
    for path, ent in collect().items():
        d = ent['data']
        if not d['root'] or (d['turns'] == 0 and not d['custom'] and not d['ai']):
            continue
        sid = os.path.basename(path)[:-6]
        known.add(sid)
        if sid in hidden:
            continue
        where = (live.get(sid) or {}).get('cwd') or d['shell'] or d['root']
        if terms and not matches(terms, d, where):
            continue
        rows.append((ent['key'][0], sid, where, d))
    rows.sort(key=lambda r: r[0], reverse=True)

    home = os.path.expanduser('~')
    write_cached('__NEW__', f"{BOLD}New session{RESET}\n\nStarts claude in {home}.\n"
                 f"Ctrl-N on any row starts a new session in that row's project instead.\n")
    write_cached('__CLOUD__', f"{BOLD}Cloud session by link{RESET}\n\nPaste a claude.ai/code link or session id and it is\n"
                 f"pulled down into a local session (claude --teleport).\n\n"
                 f"Ctrl-T on any row lists the cloud sessions for that row's project instead.\n")
    if not terms:
        print(f"__NEW__\t{home}\t+ start a new session")
        print(f"__CLOUD__\t{home}\t☁ resume a claude.ai/code session by link")
        prune_previews(known)

    for mtime, sid, where, d in rows:
        write_cached(sid, preview(sid, d, where, mtime, live.get(sid)))
        proj = os.path.basename(where.rstrip('/')) or where
        mark = f'{GREEN}●{RESET}' if sid in live else ' '
        when = time.strftime('%m-%d %H:%M', time.localtime(mtime))
        print(f"{sid}\t{where}\t{mark} {DIM}{when}{RESET}  {proj:<18.18}  {one_line(title(d), 80)}")


if __name__ == '__main__':
    main()
