#!/usr/bin/env python3
"""List Claude Code, Codex and Hermes sessions for the fzf picker and write a preview file per session."""
import glob
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

HOME = os.path.expanduser('~')
CACHE = os.environ.get('AGENT_PICKER_CACHE') or os.path.join(
    os.environ.get('XDG_CACHE_HOME', os.path.join(HOME, '.cache')), 'agent-picker')
INDEX = os.path.join(CACHE, 'index.json')
HIDDEN = os.path.join(CACHE, 'hidden.json')
INDEX_VERSION = 3
CLAUDE_HOME = os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(HOME, '.claude')
CODEX_HOME = os.environ.get('CODEX_HOME') or os.path.join(HOME, '.codex')
HERMES_HOME = os.environ.get('HERMES_HOME') or os.path.join(HOME, '.hermes')
KEEP_PROMPTS = 40
BOLD, DIM, GREEN, RESET = '\033[1m', '\033[2m', '\033[32m', '\033[0m'
AGENTS = {
    'claude': dict(bin='claude', color='\033[38;5;208m'),
    'codex': dict(bin='codex', color='\033[36m'),
    'hermes': dict(bin='hermes', color='\033[35m'),
}
CWD_RE = re.compile(r'"cwd":"([^"]*)"')
META_RE = re.compile(r'^\{"type":"([a-z-]+)"')
CLAUDE_TYPES = {'user', 'assistant', 'custom-title', 'ai-title', 'cost-state'}
SHELL_CD_RE = re.compile(r'<bash-input>\s*cd\b')
NOISE_CMDS = re.compile(r'/(compact|clear|exit|quit|model|help|cost|status|resume|usage|login|config|permissions|rename)\b')


def text_of(content, kinds=('text',)):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return '\n'.join(p.get('text', '') for p in content
                         if isinstance(p, dict) and p.get('type') in kinds)
    return ''


def new_state():
    return dict(root=None, shell=None, branch=None, custom=None, ai=None, prompts=[],
                reply=None, turns=0, cost=None, started=None, open=False)


def add_prompt(s, text):
    # Keep what the user typed: drop injected context, interruptions and repeats.
    t = (text or '').strip()
    if not t or t.startswith('<') or t.startswith('[Request interrupted') or NOISE_CMDS.match(t):
        return
    t = ' '.join(t.split())[:300]
    if s['prompts'] and s['prompts'][-1] == t:
        return
    s['turns'] += 1
    s['prompts'].append(t)
    s['prompts'] = s['prompts'][:1] + s['prompts'][1:][-KEEP_PROMPTS:]


def set_reply(s, text):
    t = (text or '').strip()
    if t:
        s['reply'] = t[:1200]


def unescape(raw):
    try:
        return json.loads(f'"{raw}"')
    except ValueError:
        return raw


def store_name(path):
    # Claude Code names a project's transcript folder after its path, one dash per other char.
    return re.sub(r'[^A-Za-z0-9-]', '-', path)


def claude_feed(s, line, store):
    # root: the project directory. shell: where the user last typed !cd.
    m = CWD_RE.search(line)
    if m:
        cwd = unescape(m.group(1))
        if not s['root'] or (store_name(cwd) == store and store_name(s['root']) != store):
            s['root'] = cwd
    m = META_RE.match(line)
    if m:
        if m.group(1) not in CLAUDE_TYPES:
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
        if d.get('isMeta') or d.get('isCompactSummary'):
            return
        m = re.search(r'<command-name>(/\S+)</command-name>', text)
        add_prompt(s, m.group(1) if m else text)
    elif t == 'assistant':
        set_reply(s, text_of((d.get('message') or {}).get('content')))
    elif t == 'custom-title':
        s['custom'] = d.get('customTitle')
    elif t == 'ai-title':
        s['ai'] = d.get('aiTitle')
    elif t == 'cost-state':
        s['cost'] = d.get('totalCostUSD')


def codex_feed(s, line, store):
    if '"type":"' not in line:
        return
    try:
        d = json.loads(line)
    except ValueError:
        return
    t, p = d.get('type'), d.get('payload') or {}
    if t == 'session_meta':
        s['root'] = s['root'] or p.get('cwd')
        s['started'] = s['started'] or p.get('timestamp') or d.get('timestamp')
        s['branch'] = (p.get('git') or {}).get('branch') or s['branch']
        if p.get('id'):
            s['sid'] = p['id']
    elif t == 'turn_context':
        s['root'] = s['root'] or p.get('cwd')
        if p.get('cwd'):
            s['shell'] = p['cwd']
    elif t == 'event_msg':
        if p.get('type') == 'user_message':
            add_prompt(s, p.get('message'))
        elif p.get('type') == 'agent_message':
            set_reply(s, p.get('message'))
    elif t == 'response_item' and p.get('type') == 'message':
        text = text_of(p.get('content'), ('input_text', 'output_text'))
        if p.get('role') == 'user':
            add_prompt(s, text)
        elif p.get('role') == 'assistant':
            set_reply(s, text)


FEEDS = {'claude': claude_feed, 'codex': codex_feed}


def scan(path, feed, s, pos):
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


def transcript_files():
    for path in glob.glob(os.path.join(CLAUDE_HOME, 'projects', '*', '*.jsonl')):
        yield 'claude', path
    for path in glob.glob(os.path.join(CODEX_HOME, 'sessions', '*', '*', '*', '*.jsonl')):
        yield 'codex', path


UUID_RE = re.compile(r'^[0-9a-fA-F-]{36}$')


def file_sid(agent, path, data):
    name = os.path.basename(path)[:-6]
    if agent == 'codex':
        sid = data.get('sid') or ''
        return sid if UUID_RE.match(sid) else name[-36:]
    return name


def load_json(path, default):
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def ensure_cache():
    # Previews and the index hold conversation text, so keep them readable by this user only.
    os.makedirs(CACHE, mode=0o700, exist_ok=True)
    try:
        os.chmod(CACHE, 0o700)
    except OSError:
        pass


def save_json(path, obj):
    ensure_cache()
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh)
    os.replace(tmp, path)


def fresh(hit, key):
    return bool(hit) and hit.get('v') == INDEX_VERSION and hit['key'] == key


def collect_files(old, new):
    for agent, path in transcript_files():
        try:
            st = os.stat(path)
        except OSError:
            continue
        key = [st.st_mtime, st.st_size]
        hit = old.get(path)
        if fresh(hit, key):
            new[path] = hit
            continue
        if hit and hit.get('v') == INDEX_VERSION and hit['pos'] <= st.st_size:
            state, pos = hit['data'], hit['pos']
        else:
            state, pos = new_state(), 0
        try:
            data, pos = scan(path, FEEDS[agent], state, pos)
        except OSError:
            continue
        new[path] = dict(v=INDEX_VERSION, key=key, pos=pos, data=data, agent=agent,
                         sid=file_sid(agent, path, data), mtime=st.st_mtime)
        save_json(INDEX, {**old, **new})


def epoch(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def collect_hermes(old, new):
    db = os.path.join(HERMES_HOME, 'state.db')
    if not os.path.exists(db):
        return
    try:
        con = sqlite3.connect(Path(db).as_uri() + '?mode=ro', uri=True)
        rows = con.execute(
            "select id, cwd, git_branch, title, title_source, started_at, ended_at, last_activity_at,"
            " message_count, estimated_cost_usd from sessions where coalesce(archived, 0) = 0").fetchall()
    except sqlite3.Error:
        return
    for sid, cwd, branch, title, title_source, started, ended, last, count, cost in rows:
        path = f'hermes:{sid}'
        mtime = epoch(last) or epoch(ended) or epoch(started)
        key = [mtime, count, ended is None and time.time() - mtime < 1800]
        hit = old.get(path)
        if fresh(hit, key):
            new[path] = hit
            continue
        s = new_state()
        s['root'], s['branch'], s['cost'] = cwd or HOME, branch, cost
        # Crashed sessions never get an end time, so only a recently active one counts as open.
        s['open'] = ended is None and time.time() - mtime < 1800
        if title_source == 'user':
            s['custom'] = title
        else:
            s['ai'] = title
        if epoch(started):
            s['started'] = time.strftime('%Y-%m-%d', time.localtime(epoch(started)))
        try:
            msgs = con.execute(
                "select role, content from messages where session_id = ? and role in ('user', 'assistant')"
                " and coalesce(content, '') != '' and coalesce(active, 1) = 1 order by id", (sid,)).fetchall()
        except sqlite3.Error:
            msgs = []
        for role, content in msgs:
            if role == 'user':
                add_prompt(s, content)
            else:
                set_reply(s, content)
        new[path] = dict(v=INDEX_VERSION, key=key, pos=0, data=s, agent='hermes', sid=sid, mtime=mtime)
    con.close()


def collect():
    old, new = load_json(INDEX, {}), {}
    collect_files(old, new)
    collect_hermes(old, new)
    if new.keys() != old.keys():
        save_json(INDEX, new)
    return new


def proc_start(pid):
    try:
        with open(f'/proc/{int(pid)}/stat') as fh:
            return fh.read().rsplit(')', 1)[1].split()[19]
    except (OSError, IndexError, TypeError, ValueError):
        return None


def pid_alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if sys.platform == 'win32':
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def session_alive(d):
    # On Linux match the process start time the lock file recorded, since pids get reused.
    if sys.platform.startswith('linux'):
        start = proc_start(d.get('pid'))
        return start is not None and (d.get('procStart') is None or str(d['procStart']) == start)
    return pid_alive(d.get('pid'))


def live_claude():
    out = {}
    for f in glob.glob(os.path.join(CLAUDE_HOME, 'sessions', '*.json')):
        d = load_json(f, {})
        if d.get('sessionId') and session_alive(d):
            out[d['sessionId']] = dict(status=d.get('status') or 'open', cwd=d.get('cwd'))
    return out


def installed():
    path = os.environ.get('PATH', '') + os.pathsep + os.path.join(HOME, '.local', 'bin')
    return [a for a, spec in AGENTS.items() if shutil.which(spec['bin'], path=path)]


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


def preview(agent, sid, d, where, mtime, live):
    cost = f"${d['cost']:.2f}" if isinstance(d['cost'], (int, float)) else '-'
    started = '-'
    if d['started']:
        try:
            started = time.strftime('%b %d', time.strptime(str(d['started'])[:10], '%Y-%m-%d'))
        except ValueError:
            pass
    color = AGENTS[agent]['color']
    out = [f"{BOLD}{title(d)}{RESET}   {color}{agent}{RESET}"]
    if live:
        out.append(f"{GREEN}● already open in another window ({live}){RESET}")
    out += [
        '',
        f"{DIM}resumes in{RESET} {where}",
        f"{DIM}project{RESET}    {d['root']}",
        f"{DIM}branch{RESET}     {d['branch'] or '-'}",
        f"{DIM}active{RESET}     {started} to {when_str(mtime)}",
        f"{DIM}prompts{RESET}    {d['turns']}    {DIM}cost{RESET} {cost}    {DIM}id{RESET} {sid[:26]}",
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


def matches(terms, agent, d, where):
    h = ' '.join([agent, title(d), where, d['root'] or '', d['branch'] or ''] + d['prompts'] + [d['reply'] or '']).lower()
    return all(t in h for t in terms)


SAFE_NAME = re.compile(r'^[A-Za-z0-9_.:-]+$')


def safe(name):
    return bool(SAFE_NAME.match(name or ''))


def write_cached(name, text):
    ensure_cache()
    path = os.path.join(CACHE, name + '.txt')
    try:
        with open(path, encoding='utf-8') as fh:
            if fh.read() == text:
                return
    except OSError:
        pass
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)


def prune_previews(keep):
    for f in glob.glob(os.path.join(CACHE, '*.txt')):
        if os.path.basename(f)[:-4] not in keep:
            try:
                os.remove(f)
            except OSError:
                pass


def claude_turns(path):
    for raw in open(path, 'rb'):
        line = raw.decode('utf-8', 'ignore')
        if '"type":"user"' not in line and '"type":"assistant"' not in line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get('isSidechain') or d.get('isMeta') or d.get('isCompactSummary'):
            continue
        text = text_of((d.get('message') or {}).get('content')).strip()
        if d.get('type') == 'user' and text and not text.startswith('<'):
            yield 'user', text
        elif d.get('type') == 'assistant' and text:
            yield 'assistant', text


def codex_turns(path):
    turns, fallback = [], []
    for raw in open(path, 'rb'):
        try:
            d = json.loads(raw.decode('utf-8', 'ignore'))
        except ValueError:
            continue
        t, p = d.get('type'), d.get('payload') or {}
        if t == 'event_msg' and p.get('type') in ('user_message', 'agent_message') and p.get('message'):
            turns.append(('user' if p['type'] == 'user_message' else 'assistant', p['message'].strip()))
        elif t == 'response_item' and p.get('type') == 'message' and p.get('role') in ('user', 'assistant'):
            text = text_of(p.get('content'), ('input_text', 'output_text')).strip()
            if text and not text.startswith('<'):
                fallback.append((p['role'], text))
    return turns or fallback


def hermes_turns(sid):
    con = sqlite3.connect(Path(os.path.join(HERMES_HOME, 'state.db')).as_uri() + '?mode=ro', uri=True)
    rows = con.execute("select role, content from messages where session_id = ? and role in ('user', 'assistant')"
                       " and coalesce(content, '') != '' and coalesce(active, 1) = 1 order by id", (sid,)).fetchall()
    con.close()
    return [(r, c.strip()) for r, c in rows]


def export_markdown(agent, sid, out, limit=200000):
    # Writes the conversation so another agent can pick it up; keeps the tail when it is long.
    ent = next((e for e in load_json(INDEX, {}).items() if e[1].get('agent') == agent and e[1].get('sid') == sid), None)
    if not ent:
        return False
    path, d = ent[0], ent[1]['data']
    if agent == 'claude':
        turns = list(claude_turns(path))
    elif agent == 'codex':
        turns = codex_turns(path)
    else:
        turns = hermes_turns(sid)
    body, total = [], 0
    for role, text in reversed(turns):
        total += len(text)
        if total > limit:
            body.append('_(earlier turns omitted)_')
            break
        body.append(f"**{'You' if role == 'user' else agent}:**\n\n{text}")
    head = [f"# Handoff from a {agent} session", '', f"- title: {title(d)}", f"- project: {d['root']}",
            f"- branch: {d['branch'] or '-'}", f"- session id: {sid}", '', '## Conversation', '']
    ensure_cache()
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(head) + '\n\n'.join(reversed(body)) + '\n')
    return True


def copy_text(text):
    for cmd in (['pbcopy'], ['clip'], ['wl-copy'], ['xclip', '-selection', 'clipboard'], ['xsel', '--clipboard', '--input']):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, input=text.encode(), check=False)
            return True
    return False


def watched_files():
    paths = glob.glob(os.path.join(CLAUDE_HOME, 'projects', '*', '*.jsonl'))
    paths += glob.glob(os.path.join(CODEX_HOME, 'sessions', '*', '*', '*', '*.jsonl'))
    paths += [os.path.join(HERMES_HOME, 'state.db'), os.path.join(HERMES_HOME, 'state.db-wal')]
    return paths


def session_rows(terms, live, hidden):
    rows, known = [], set()
    for ent in collect().values():
        agent, sid, d = ent['agent'], ent['sid'], ent['data']
        if not d['root'] or (d['turns'] == 0 and not d['custom'] and not d['ai']):
            continue
        name = f'{agent}-{sid}'
        known.add(name)
        if f'{agent}:{sid}' in hidden:
            continue
        status = None
        if agent == 'claude' and sid in live:
            status = live[sid]['status']
        elif d.get('open'):
            status = 'open'
        where = (live.get(sid) or {}).get('cwd') if agent == 'claude' else None
        where = where or d['shell'] or d['root']
        if terms and not matches(terms, agent, d, where):
            continue
        rows.append((ent['mtime'], agent, sid, where, d, status))
    rows.sort(key=lambda r: r[0], reverse=True)
    return rows, known


def list_sessions(terms, as_json=False):
    live = live_claude()
    hidden = set(load_json(HIDDEN, []))
    agents = installed()
    rows, known = session_rows(terms, live, hidden)
    if as_json:
        print(json.dumps([dict(agent=a, id=sid, dir=where, project=d['root'], branch=d['branch'], title=title(d),
                               last_active=time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(m)), prompts=d['turns'],
                               cost_usd=d['cost'], open=bool(st), first_prompt=d['prompts'][0] if d['prompts'] else None,
                               last_reply=d['reply']) for m, a, sid, where, d, st in rows], indent=2))
        return
    for agent in agents:
        known.add(f'{agent}-__NEW__')
        write_cached(f'{agent}-__NEW__', f"{BOLD}New {agent} session{RESET}\n\nStarts {agent} in {HOME}.\n"
                     f"Ctrl-N on any row starts a new session of that row's agent in its directory instead.\n")
        if not terms:
            color = AGENTS[agent]['color']
            print(f"{agent}\t__NEW__\t{HOME}\t+ new {color}{agent}{RESET} session")
    if 'claude' in agents:
        known.add('claude-__CLOUD__')
        write_cached('claude-__CLOUD__', f"{BOLD}Cloud session by link{RESET}\n\nPaste a claude.ai/code link or session id and it is\n"
                     f"pulled down into a local session (claude --teleport).\n\n"
                     f"Ctrl-T on a claude row lists the cloud sessions for that row's directory instead.\n")
        if not terms:
            print(f"claude\t__CLOUD__\t{HOME}\t\u2601 resume a claude.ai/code session by link")
    if not terms:
        prune_previews(known)
    for mtime, agent, sid, where, d, status in rows:
        write_cached(f'{agent}-{sid}', preview(agent, sid, d, where, mtime, status))
        proj = os.path.basename(where.rstrip('/')) or where
        mark = f'{GREEN}●{RESET}' if status else ' '
        when = time.strftime('%m-%d %H:%M', time.localtime(mtime))
        color = AGENTS[agent]['color']
        print(f"{agent}\t{sid}\t{where}\t{mark} {DIM}{when}{RESET}  {color}{agent:<6}{RESET}  {proj:<18.18}  {one_line(title(d), 80)}")


def show_preview(agent, sid, full):
    if full:
        out = os.path.join(CACHE, f'full-{agent}-{sid}.md')
        if export_markdown(agent, sid, out):
            with open(out, encoding='utf-8') as fh:
                sys.stdout.write(fh.read())
        return
    try:
        with open(os.path.join(CACHE, f'{agent}-{sid}.txt'), encoding='utf-8') as fh:
            sys.stdout.write(fh.read())
    except OSError:
        pass


def doctor():
    import platform
    print(f"aisp on {platform.system()} {platform.release()}, python {platform.python_version()}")
    fzf = shutil.which('fzf')
    if fzf:
        ver = subprocess.run([fzf, '--version'], capture_output=True, text=True).stdout.split()[:1]
        print(f"fzf        {fzf} {' '.join(ver)}")
    else:
        print('fzf        MISSING, install it from https://github.com/junegunn/fzf#installation')
    print(f'cache      {CACHE}')
    stores = [('claude', CLAUDE_HOME, os.path.join(CLAUDE_HOME, 'projects', '*', '*.jsonl')),
              ('codex', CODEX_HOME, os.path.join(CODEX_HOME, 'sessions', '*', '*', '*', '*.jsonl')),
              ('hermes', HERMES_HOME, os.path.join(HERMES_HOME, 'state.db'))]
    found = installed()
    for agent, home, pattern in stores:
        exe = shutil.which(AGENTS[agent]['bin']) or 'not on PATH'
        n = len(glob.glob(pattern))
        store = f"{n} transcript(s)" if agent != 'hermes' else ('store present' if n else 'no store')
        print(f"{agent:<10} {exe}")
        print(f"{'':<10} {home}: {store}")
    rows, _ = session_rows([], live_claude(), set(load_json(HIDDEN, [])))
    print(f"sessions   {len(rows)} listed, {len(load_json(HIDDEN, []))} hidden, agents installed: {', '.join(found) or 'none'}")
    return 0 if fzf and found else 1


USAGE = """aisp                       pick a session and resume it
aisp --window              same, in a new terminal window
aisp list [--json] [words]  print the session list (words filter it)
aisp doctor                check agents, stores, fzf and the cache
aisp preview [--full] AGENT ID
aisp export AGENT ID FILE   write a session as markdown
aisp hide AGENT ID | aisp unhide-all | aisp copy TEXT"""


def main(argv=None):
    os.umask(0o077)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    args = list(sys.argv[1:] if argv is None else argv)
    cmd, rest = (args[0] if args else 'list'), args[1:]
    if cmd in ('hide', 'preview', 'export'):
        ids = [a for a in rest if not a.startswith('--')]
        if len(ids) < 2 or not (safe(ids[0]) and safe(ids[1])):
            sys.exit('aisp: bad agent or session id')
    if cmd == 'list':
        as_json = '--json' in rest
        return list_sessions(' '.join(a for a in rest if a != '--json').lower().split(), as_json)
    if cmd == 'hide':
        return save_json(HIDDEN, sorted(set(load_json(HIDDEN, [])) | {f'{rest[0]}:{rest[1]}'}))
    if cmd == 'unhide-all':
        return save_json(HIDDEN, [])
    if cmd == 'preview':
        ids = [a for a in rest if not a.startswith('--')]
        return show_preview(ids[0], ids[1], '--full' in rest)
    if cmd == 'export' and len(rest) == 3:
        if not export_markdown(rest[0], rest[1], rest[2]):
            sys.exit('aisp: session not found')
        return
    if cmd == 'copy' and len(rest) == 1:
        return copy_text(rest[0])
    if cmd == 'doctor':
        sys.exit(doctor())
    sys.exit(f'usage:\n{USAGE}')


if __name__ == '__main__':
    main()
