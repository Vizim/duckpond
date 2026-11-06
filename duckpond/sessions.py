#!/usr/bin/env python3
"""List Claude Code, Codex and Hermes sessions for the fzf picker and write a preview file per session."""
import calendar
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
CACHE = os.environ.get('DUCKPOND_CACHE') or os.path.join(
    os.environ.get('XDG_CACHE_HOME', os.path.join(HOME, '.cache')), 'duckpond')
INDEX = os.path.join(CACHE, 'index.json')
HIDDEN = os.path.join(CACHE, 'hidden.json')
INDEX_VERSION = 12
CLAUDE_HOME = os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(HOME, '.claude')
CODEX_HOME = os.environ.get('CODEX_HOME') or os.path.join(HOME, '.codex')
HERMES_HOME = os.environ.get('HERMES_HOME') or os.path.join(HOME, '.hermes')
COPILOT_HOME = os.environ.get('COPILOT_HOME') or os.path.join(HOME, '.copilot')


def vscode_user_dir():
    # VS Code's User directory, where Copilot Chat sessions live under workspaceStorage.
    if os.environ.get('DUCKPOND_VSCODE_DIR'):
        return os.environ['DUCKPOND_VSCODE_DIR']
    if sys.platform == 'win32':
        return os.path.join(os.environ.get('APPDATA', HOME), 'Code', 'User')
    if sys.platform == 'darwin':
        return os.path.join(HOME, 'Library', 'Application Support', 'Code', 'User')
    return os.path.join(os.environ.get('XDG_CONFIG_HOME', os.path.join(HOME, '.config')), 'Code', 'User')


VSCODE_USER = vscode_user_dir()
KEEP_PROMPTS = 40
KEEP_TIMES = 400
KEEP_MINUTES = 1500
RECENT_OPEN_SECONDS = 900
LOCKLESS = ('codex', 'copilot', 'vscode')
BUSY_SECONDS = 20
BOLD, DIM, GREEN, RESET = '\033[1m', '\033[2m', '\033[32m', '\033[0m'
AGENTS = {
    'claude': dict(bin='claude', color='\033[38;5;208m'),
    'codex': dict(bin='codex', color='\033[36m'),
    'hermes': dict(bin='hermes', color='\033[35m'),
    'copilot': dict(bin='copilot', color='\033[38;5;75m'),
    'vscode': dict(bin='code', color='\033[38;5;39m'),
}
CWD_RE = re.compile(r'"cwd":"([^"]*)"')
META_RE = re.compile(r'^\{"type":"([a-z-]+)"')
CLAUDE_TYPES = {'user', 'assistant', 'custom-title', 'ai-title', 'cost-state'}
SHELL_CD_RE = re.compile(r'<bash-input>\s*cd\b')
TOOL_RE = re.compile(r'"type":"tool_use","id":"[^"]*","name":"([A-Za-z_]+)"')
USAGE_FIELDS = {k: re.compile(r'"%s":(\d+)' % k) for k in
                ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens')}
MSG_ID_RE = re.compile(r'"id":"(msg_[^"]+)"')
TS_RE = re.compile(r'"timestamp":"([^"]+)"')
TASK_DONE_RE = re.compile(r'<tool-use-id>(toolu_[^<]+)</tool-use-id>')
TOOL_DETAIL_RE = {k: re.compile(r'"%s":"((?:[^"\\]|\\.){1,160})' % k) for k in ('description', 'file_path', 'pattern', 'command')}
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
                reply=None, turns=0, cost=None, started=None, open=False, tool=None, times=[], subagents={}, tok=[], ctx=0)


def to_epoch(v):
    # Milliseconds, seconds or an ISO timestamp, as seconds since the epoch; None when unreadable.
    if isinstance(v, (int, float)):
        return v / 1000 if v > 1e11 else float(v)
    if isinstance(v, str) and len(v) >= 19:
        try:
            return float(calendar.timegm(time.strptime(v[:19], '%Y-%m-%dT%H:%M:%S')))
        except ValueError:
            return None
    return None


def add_prompt(s, text, when=None):
    # Keep what the user typed: drop injected context, interruptions and repeats.
    t = (text or '').strip()
    # Bracketed and tagged lines are things the harness injected, not something the user typed.
    if (not t or t.startswith('<') or t.startswith('[')
            or t.startswith('Another Claude session sent a message') or NOISE_CMDS.match(t)):
        return
    t = ' '.join(t.split())[:300]
    if s['prompts'] and s['prompts'][-1] == t:
        return
    s['turns'] += 1
    s['prompts'].append(t)
    ts = to_epoch(when)
    if ts:
        s.setdefault('times', []).append(round(ts))
        del s['times'][:-KEEP_TIMES]
    s['prompts'] = s['prompts'][:1] + s['prompts'][1:][-KEEP_PROMPTS:]


def add_tokens(s, when, tin, tout, cached=0):
    # Tokens in, out and cached-in, summed per minute, so the pond can graph them like network traffic.
    ts = to_epoch(when)
    if not ts or not (tin or tout):
        return
    minute = int(ts // 60) * 60
    tok = s.setdefault('tok', [])
    if tok and tok[-1][0] == minute:
        tok[-1][1] += tin
        tok[-1][2] += tout
        tok[-1][3] += cached
    else:
        tok.append([minute, tin, tout, cached])
        del tok[:-KEEP_MINUTES]


def num(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def claude_usage(s, line):
    # Each content block of one reply repeats the same usage, so count a message id once.
    at = line.rfind('"usage":{')
    if at < 0:
        return
    mid = MSG_ID_RE.search(line)
    mid = mid.group(1) if mid else None
    if mid and mid == s.get('last_msg'):
        return
    s['last_msg'] = mid
    f = {}
    for key, rx in USAGE_FIELDS.items():
        m = rx.search(line, at)
        f[key] = num(m.group(1)) if m else 0
    tin = f['input_tokens'] + f['cache_creation_input_tokens'] + f['cache_read_input_tokens']
    s['ctx'] = tin
    stamps = TS_RE.findall(line)
    add_tokens(s, stamps[-1] if stamps else None, tin, f['output_tokens'], f['cache_read_input_tokens'])


def set_tool(s, line):
    # Which tool the agent just called and, briefly, on what. Agent calls start a subagent.
    blocks = list(TOOL_RE.finditer(line))
    stamps = TS_RE.findall(line)
    started = round(to_epoch(stamps[-1]) or time.time()) if stamps else round(time.time())
    for i, m in enumerate(blocks):
        end = blocks[i + 1].start() if i + 1 < len(blocks) else len(line)
        detail = ''
        for key in ('description', 'file_path', 'pattern', 'command'):
            d = TOOL_DETAIL_RE[key].search(line, m.end(), end)
            if d:
                detail = unescape(d.group(1))
                if key == 'file_path':
                    detail = os.path.basename(detail)
                break
        s['tool'] = ' '.join([m.group(1), one_line(detail, 70)]).strip()
        tid = re.search(r'"id":"([^"]*)"', m.group(0)).group(1)
        if m.group(1) == 'Agent' and tid:
            subs = s.setdefault('subagents', {})
            subs[tid] = [one_line(detail, 40) or 'subagent', started]
            for old in list(subs)[:-8]:
                del subs[old]


def end_subagents(s, content):
    # A subagent ends with its tool result, unless it was launched in the background: then a task
    # notification naming the same tool-use id arrives later.
    subs = s.get('subagents')
    if not subs:
        return
    if isinstance(content, str):
        for tid in TASK_DONE_RE.findall(content):
            subs.pop(tid, None)
        return
    for part in content if isinstance(content, list) else ():
        if not isinstance(part, dict):
            continue
        if part.get('type') == 'tool_result':
            tid = part.get('tool_use_id')
            if tid in subs and 'Async agent launched' not in text_of(part.get('content')):
                subs.pop(tid)
        elif part.get('type') == 'text':
            for tid in TASK_DONE_RE.findall(part.get('text') or ''):
                subs.pop(tid, None)


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
    if 'task-notification' in line and s.get('subagents'):
        # Background agents finish on whatever line type carries the notification, so read it raw.
        for tid in TASK_DONE_RE.findall(line):
            s['subagents'].pop(tid, None)
    m = META_RE.match(line)
    kind = m.group(1) if m else None
    if kind == 'queue-operation' and '"operation":"enqueue"' in line:
        # Messages typed while the agent is busy are queued, and only sometimes replayed as user lines.
        try:
            d = json.loads(line)
        except ValueError:
            return
        add_prompt(s, d.get('content') if isinstance(d.get('content'), str) else '', d.get('timestamp'))
        return
    if kind and kind not in CLAUDE_TYPES:
        return
    if kind == 'assistant' or (not kind and '"type":"assistant"' in line):
        claude_usage(s, line)
        if '"type":"tool_use"' in line and '"isSidechain":false' in line:
            set_tool(s, line)
        if '"type":"text"' not in line:
            return
    elif not kind and '"type":"user"' not in line:
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
        end_subagents(s, (d.get('message') or {}).get('content'))
        text = text_of((d.get('message') or {}).get('content'))
        if SHELL_CD_RE.search(text) and d.get('cwd'):
            s['shell'] = d['cwd']
        if d.get('isMeta') or d.get('isCompactSummary'):
            return
        m = re.search(r'<command-name>(/\S+)</command-name>', text)
        add_prompt(s, m.group(1) if m else text, d.get('timestamp'))
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
        kind = p.get('type')
        if kind == 'token_count':
            info = p.get('info') or {}
            last = info.get('last_token_usage') or {}
            add_tokens(s, d.get('timestamp'), num(last.get('input_tokens')), num(last.get('output_tokens')),
                       num(last.get('cached_input_tokens')))
            s['ctx'] = num(last.get('input_tokens'))
            if num(info.get('model_context_window')):
                s['ctx_limit'] = num(info.get('model_context_window'))
        elif kind == 'task_started':
            s['busy'] = True
        elif kind in ('task_complete', 'turn_aborted', 'error'):
            s['busy'] = False
        elif kind == 'user_message':
            add_prompt(s, p.get('message'), d.get('timestamp'))
        elif p.get('type') == 'agent_message':
            set_reply(s, p.get('message'))
    elif t == 'response_item' and p.get('type') in ('function_call', 'custom_tool_call', 'local_shell_call'):
        try:
            args = json.loads(p.get('arguments') or '{}') if isinstance(p.get('arguments'), str) else (p.get('arguments') or {})
        except ValueError:
            args = {}
        cmd = (args.get('command') or args.get('cmd')) if isinstance(args, dict) else None
        if p.get('type') == 'local_shell_call':
            cmd = ((p.get('action') or {}).get('command'))
        cmd = ' '.join(cmd) if isinstance(cmd, list) else cmd
        s['tool'] = ' '.join([str(p.get('name') or p.get('type')), one_line(str(cmd or ''), 70)]).strip()
    elif t == 'response_item' and p.get('type') == 'message':
        text = text_of(p.get('content'), ('input_text', 'output_text'))
        if p.get('role') == 'user':
            add_prompt(s, text, d.get('timestamp'))
        elif p.get('role') == 'assistant':
            set_reply(s, text)


def copilot_feed(s, line, store):
    # Copilot CLI events.jsonl: one event per line with type, timestamp and data.
    if '"type":"' not in line:
        return
    try:
        d = json.loads(line)
    except ValueError:
        return
    t, data, when = d.get('type'), d.get('data') or {}, d.get('timestamp')
    if t in ('session.start', 'session.resume'):
        cwd = (data.get('context') or {}).get('cwd')
        s['root'] = s['root'] or cwd
        if cwd:
            s['shell'] = cwd
        s['started'] = s['started'] or data.get('startTime') or when
    elif t == 'user.message':
        add_prompt(s, data.get('content'), when)
    elif t == 'assistant.turn_start':
        s['busy'] = True
    elif t in ('assistant.turn_end', 'session.truncation'):
        s['busy'] = False
    elif t == 'assistant.message':
        set_reply(s, data.get('content'))
        for req in data.get('toolRequests') or ():
            if isinstance(req, dict):
                args = req.get('arguments')
                detail = ''
                if isinstance(args, dict):
                    detail = str(args.get('command') or args.get('path') or args.get('description') or '')
                s['tool'] = ' '.join([str(req.get('name') or 'tool'), one_line(detail, 70)]).strip()


def part_text(part):
    # The text in one serialized VS Code chat response part, if it has any.
    if isinstance(part, str):
        return part
    if not isinstance(part, dict):
        return ''
    kind = part.get('kind')
    if kind == 'markdownContent':
        content = part.get('content')
        return content.get('value', '') if isinstance(content, dict) else str(content or '')
    if kind is None and isinstance(part.get('value'), str):
        return part['value']
    return ''


def part_tool(part):
    if isinstance(part, dict) and part.get('kind') in ('toolInvocationSerialized', 'toolInvocation'):
        return str(part.get('toolId') or part.get('toolCallId') or 'tool')
    return None


def vscode_request(s, req):
    msg = req.get('message')
    text = msg.get('text') if isinstance(msg, dict) else msg
    add_prompt(s, text, req.get('timestamp'))
    parts = req.get('response') or []
    set_reply(s, ''.join(part_text(p) for p in parts))
    for p in parts:
        tool = part_tool(p)
        if tool:
            s['tool'] = tool
    s['busy'] = req.get('result') is None
    s['n'] = s.get('n', 0) + 1


def vscode_feed(s, line, store):
    # VS Code chat sessions are a mutation log: an initial snapshot, then set and push records with paths.
    try:
        d = json.loads(line)
    except ValueError:
        return
    kind, k, v = d.get('kind'), d.get('k') or [], d.get('v')
    if kind == 0 and isinstance(v, dict):
        s['custom'] = v.get('customTitle') or s['custom']
        s['started'] = s['started'] or v.get('creationDate')
        s['root'] = s['root'] or v.get('workingDirectory')
        s['n'] = 0
        for req in v.get('requests') or ():
            if isinstance(req, dict):
                vscode_request(s, req)
    elif kind == 1 and k == ['customTitle']:
        s['custom'] = v
    elif kind == 2 and k == ['requests']:
        if d.get('i') is not None:
            s['n'] = min(s.get('n', 0), d['i'])
        for req in v or ():
            if isinstance(req, dict):
                vscode_request(s, req)
    elif len(k) >= 3 and k[0] == 'requests' and k[1] == s.get('n', 0) - 1:
        # Changes to the latest request: a streamed response, its result, or a title set by the user.
        if k[2] == 'response' and kind == 2 and isinstance(v, list):
            set_reply(s, (s['reply'] or '') + ''.join(part_text(p) for p in v))
            for p in v:
                tool = part_tool(p)
                if tool:
                    s['tool'] = tool
        elif k[2] == 'response' and kind == 1 and len(k) == 3 and isinstance(v, list):
            set_reply(s, ''.join(part_text(p) for p in v))
        elif k[2] == 'result' and kind in (1, 2):
            s['busy'] = False


FEEDS = {'claude': claude_feed, 'codex': codex_feed, 'copilot': copilot_feed, 'vscode': vscode_feed}


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
    for path in glob.glob(os.path.join(COPILOT_HOME, 'session-state', '*', 'events.jsonl')) + glob.glob(
            os.path.join(COPILOT_HOME, 'session-state', '*.jsonl')):
        yield 'copilot', path
    for path in glob.glob(os.path.join(VSCODE_USER, 'workspaceStorage', '*', 'chatSessions', '*.jsonl')) + glob.glob(
            os.path.join(VSCODE_USER, 'globalStorage', 'emptyWindowChatSessions', '*.jsonl')):
        yield 'vscode', path


UUID_RE = re.compile(r'^[0-9a-fA-F-]{36}$')


def file_sid(agent, path, data):
    name = os.path.basename(path)[:-6]
    if agent == 'codex':
        sid = data.get('sid') or ''
        return sid if UUID_RE.match(sid) else name[-36:]
    if agent == 'copilot' and name == 'events':
        return os.path.basename(os.path.dirname(path))
    return name


def vscode_root(path):
    # The workspace a VS Code chat belongs to is in workspace.json beside its chatSessions folder.
    meta = os.path.join(os.path.dirname(os.path.dirname(path)), 'workspace.json')
    folder = load_json(meta, {}).get('folder') or ''
    if folder.startswith('file://'):
        from urllib.parse import unquote, urlparse
        p = unquote(urlparse(folder).path)
        if sys.platform == 'win32' and re.match(r'^/[A-Za-z]:', p):
            p = p[1:]
        return p
    return folder or HOME


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
        if agent == 'vscode' and not data['root']:
            data['root'] = vscode_root(path)
        new[path] = dict(v=INDEX_VERSION, key=key, pos=pos, data=data, agent=agent,
                         sid=file_sid(agent, path, data), mtime=st.st_mtime)
        save_json(INDEX, {**old, **new})


def epoch(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def hermes_columns(con, table):
    try:
        return {row[1] for row in con.execute(f'pragma table_info({table})')}
    except sqlite3.Error:
        return set()


def hermes_children(con, cols):
    # Subagents are child sessions; the ones still running become ducklings on their parent.
    if 'parent_session_id' not in cols:
        return {}
    out = {}
    try:
        rows = con.execute("select id, parent_session_id, title, started_at from sessions"
                           " where parent_session_id is not null and ended_at is null").fetchall()
        for cid, parent, title, started in rows:
            label = title
            if not label:
                row = con.execute("select content from messages where session_id = ? and role = 'user'"
                                  " and coalesce(content, '') != '' order by id limit 1", (cid,)).fetchone()
                label = row[0] if row else ''
            out.setdefault(parent, {})[cid] = [one_line(label, 40) or 'subagent', round(epoch(started))]
    except sqlite3.Error:
        pass
    return out


def collect_hermes(old, new):
    db = os.path.join(HERMES_HOME, 'state.db')
    if not os.path.exists(db):
        return
    try:
        con = sqlite3.connect(Path(db).as_uri() + '?mode=ro', uri=True)
        cols = hermes_columns(con, 'sessions')
        msg_cols = hermes_columns(con, 'messages')
        want = ['id', 'cwd', 'git_branch', 'title', 'title_source', 'started_at', 'ended_at', 'last_activity_at',
                'message_count', 'estimated_cost_usd', 'input_tokens', 'output_tokens', 'cache_read_tokens', 'api_call_count']
        select = ', '.join(c if c in cols else f'null as {c}' for c in want)
        parents = "coalesce(archived, 0) = 0" + (" and parent_session_id is null" if 'parent_session_id' in cols else '')
        rows = con.execute(f"select {select} from sessions where {parents}").fetchall()
        children = hermes_children(con, cols)
    except sqlite3.Error:
        return
    for sid, cwd, branch, title, title_source, started, ended, last, count, cost, tin, tout, cached, calls in rows:
        path = f'hermes:{sid}'
        mtime = epoch(last) or epoch(ended) or epoch(started)
        subs = children.get(sid, {})
        key = [mtime, count, ended is None and time.time() - mtime < 1800, sorted(subs)]
        hit = old.get(path)
        if fresh(hit, key):
            new[path] = hit
            continue
        s = new_state()
        s['root'], s['branch'], s['cost'] = cwd or HOME, branch, cost
        # Crashed sessions never get an end time, so only a recently active one counts as open.
        s['open'] = ended is None and time.time() - mtime < 1800
        s['subagents'] = subs
        if title_source == 'user':
            s['custom'] = title
        else:
            s['ai'] = title
        if epoch(started):
            s['started'] = time.strftime('%Y-%m-%d', time.localtime(epoch(started)))
        try:
            msgs = con.execute(
                "select role, content, timestamp, token_count from messages where session_id = ?"
                " and role in ('user', 'assistant') and coalesce(content, '') != '' and coalesce(active, 1) = 1"
                " order by id", (sid,)).fetchall()
            tool = None
            if 'tool_name' in msg_cols:
                row = con.execute("select tool_name from messages where session_id = ? and tool_name is not null"
                                  " order by id desc limit 1", (sid,)).fetchone()
                tool = row[0] if row else None
        except sqlite3.Error:
            msgs, tool = [], None
        for role, content, when, per_msg in msgs:
            per_msg = num(per_msg)
            if role == 'user':
                add_prompt(s, content, when)
                add_tokens(s, when, per_msg, 0)
            else:
                set_reply(s, content)
                add_tokens(s, when, 0, per_msg)
        if num(tin) or num(tout):
            # Hermes keeps token totals per session rather than per message; context is the mean per API call.
            s['tok'] = [[int(mtime // 60) * 60, num(tin), num(tout), num(cached)]]
            s['ctx'] = (num(tin) + num(cached)) // max(1, num(calls))
        s['tool'] = tool
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
            out[d['sessionId']] = dict(status=d.get('status') or 'open', cwd=d.get('cwd'), name=d.get('name'),
                                       started=d.get('startedAt'), since=d.get('statusUpdatedAt'))
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


def copilot_turns(path):
    for raw in open(path, 'rb'):
        try:
            d = json.loads(raw.decode('utf-8', 'ignore'))
        except ValueError:
            continue
        data = d.get('data') or {}
        if d.get('type') == 'user.message' and (data.get('content') or '').strip():
            yield 'user', data['content'].strip()
        elif d.get('type') == 'assistant.message' and (data.get('content') or '').strip():
            yield 'assistant', data['content'].strip()


def vscode_turns(path):
    requests = []
    for raw in open(path, 'rb'):
        try:
            d = json.loads(raw.decode('utf-8', 'ignore'))
        except ValueError:
            continue
        kind, k, v = d.get('kind'), d.get('k') or [], d.get('v')
        if kind == 0 and isinstance(v, dict):
            requests = [r for r in v.get('requests') or () if isinstance(r, dict)]
        elif kind == 2 and k == ['requests']:
            if d.get('i') is not None:
                del requests[d['i']:]
            requests += [r for r in v or () if isinstance(r, dict)]
        elif len(k) == 3 and k[0] == 'requests' and k[2] == 'response' and isinstance(k[1], int) and k[1] < len(requests):
            if kind == 2:
                requests[k[1]]['response'] = list(requests[k[1]].get('response') or []) + list(v or [])
            elif kind == 1:
                requests[k[1]]['response'] = v
    for r in requests:
        msg = r.get('message')
        text = (msg.get('text') if isinstance(msg, dict) else msg) or ''
        if text.strip():
            yield 'user', text.strip()
        reply = ''.join(part_text(p) for p in r.get('response') or [])
        if reply.strip():
            yield 'assistant', reply.strip()


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
    elif agent == 'copilot':
        turns = list(copilot_turns(path))
    elif agent == 'vscode':
        turns = list(vscode_turns(path))
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


def newest(terms):
    rows, _ = session_rows(terms, live_claude(), set(load_json(HIDDEN, [])))
    return rows[0] if rows else None


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
        age = time.time() - ent['mtime']
        if agent == 'claude' and sid in live:
            status = live[sid]['status']
        elif d.get('open') or (agent in LOCKLESS and age < RECENT_OPEN_SECONDS):
            # No lock file for these: recent writes mean open; a turn in progress or a very recent write means busy.
            status = 'busy' if age < BUSY_SECONDS or (agent in LOCKLESS and d.get('busy')) else 'open'
        # A cd you typed wins, then the directory a live session was launched from, then the project.
        launched = (live.get(sid) or {}).get('cwd') if agent == 'claude' else None
        where = d['shell'] or launched or d['root']
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
    from .duck import DUCK
    print(DUCK)
    print(f"duckpond on {platform.system()} {platform.release()}, python {platform.python_version()}")
    from . import hints
    fzf = shutil.which('fzf')
    if fzf:
        ver = subprocess.run([fzf, '--version'], capture_output=True, text=True).stdout.split()[:1]
        print(f"fzf        {fzf} {' '.join(ver)}")
    else:
        print(f'fzf        MISSING. {hints.fzf_hint()}')
    print(f'cache      {CACHE}')
    from . import config
    print(f"terminal   {config.get('terminal') or 'auto'}    (duckpond config terminal \"...\" to change)")
    stores = [('claude', CLAUDE_HOME, os.path.join(CLAUDE_HOME, 'projects', '*', '*.jsonl')),
              ('codex', CODEX_HOME, os.path.join(CODEX_HOME, 'sessions', '*', '*', '*', '*.jsonl')),
              ('hermes', HERMES_HOME, os.path.join(HERMES_HOME, 'state.db')),
              ('copilot', COPILOT_HOME, os.path.join(COPILOT_HOME, 'session-state', '*', 'events.jsonl')),
              ('vscode', VSCODE_USER, os.path.join(VSCODE_USER, 'workspaceStorage', '*', 'chatSessions', '*.jsonl'))]
    found = installed()
    for agent, home, pattern in stores:
        exe = shutil.which(AGENTS[agent]['bin']) or f'not on PATH. {hints.agent_hint(agent).split(". ", 1)[1]}'
        n = len(glob.glob(pattern))
        store = f"{n} transcript(s)" if agent != 'hermes' else ('store present' if n else 'no store')
        print(f"{agent:<10} {exe}")
        print(f"{'':<10} {home}: {store}")
    rows, _ = session_rows([], live_claude(), set(load_json(HIDDEN, [])))
    print(f"sessions   {len(rows)} listed, {len(load_json(HIDDEN, []))} hidden, agents installed: {', '.join(found) or 'none'}")
    print()
    if fzf and found and rows:
        print(f"{GREEN}ready.{RESET} run: duckpond")
    elif fzf and found:
        print(f"{GREEN}ready{RESET}, no sessions yet. run {' or '.join(found)} once and it will show up here.")
    elif not fzf:
        print(hints.fzf_hint())
    else:
        print(hints.no_agents_hint())
    return 0 if fzf and found else 1


USAGE = """duckpond                       pick a session and resume it
duckpond --window              same, in a new terminal window
duckpond list [--json] [words]  print the session list (words filter it)
duckpond doctor                check agents, stores, fzf and the cache
duckpond pond [--interval S] [--once|--demo]  the btop-style heads-up display
duckpond config [KEY [VALUE]]  show or change settings, e.g. duckpond config terminal "alacritty -e"
duckpond install-launcher      add an "AI Sessions" app with an icon to this desktop
duckpond uninstall-launcher    remove it again
duckpond install-skills [AGENT...]  teach Claude Code, Codex and Hermes about duckpond and handoffs
duckpond uninstall-skills      remove those skill files
duckpond preview [--full] AGENT ID
duckpond export AGENT ID FILE   write a session as markdown
duckpond hide AGENT ID | duckpond unhide-all | duckpond copy TEXT
don't feel like typing duckpond? aisp does exactly the same thing"""


def main(argv=None):
    os.umask(0o077)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    args = list(sys.argv[1:] if argv is None else argv)
    cmd, rest = (args[0] if args else 'list'), args[1:]
    if cmd in ('hide', 'preview', 'export'):
        ids = [a for a in rest if not a.startswith('--')]
        if len(ids) < 2 or not (safe(ids[0]) and safe(ids[1])):
            sys.exit('duckpond: bad agent or session id')
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
            sys.exit('duckpond: session not found')
        return
    if cmd == 'copy' and len(rest) == 1:
        return copy_text(rest[0])
    if cmd == 'doctor':
        sys.exit(doctor())
    sys.exit(f'usage:\n{USAGE}')


if __name__ == '__main__':
    main()
