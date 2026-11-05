"""Build sample Claude, Codex and Hermes session stores under a root dir for tests and screenshots."""
import json
import os
import sqlite3
import sys
import time
import uuid

HOME = '/home/ada'


def iso(ts):
    return time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(ts))


def dumps(obj):
    return json.dumps(obj, separators=(',', ':'))


def claude_session(root, project, title, prompts, reply, age_h, cost, live=False, now=None):
    now = now or time.time()
    store = project.replace('/', '-').replace('.', '-')
    d = os.path.join(root, 'claude', 'projects', store)
    os.makedirs(d, exist_ok=True)
    sid = str(uuid.uuid4())
    t0 = now - age_h * 3600
    lines = [{'type': 'permission-mode', 'permissionMode': 'default', 'sessionId': sid}]
    for i, p in enumerate(prompts):
        ts = t0 + i * 600
        lines.append({'parentUuid': None, 'isSidechain': False, 'type': 'user', 'cwd': project, 'gitBranch': 'main',
                      'timestamp': iso(ts), 'sessionId': sid, 'message': {'role': 'user', 'content': p}})
        lines.append({'parentUuid': None, 'isSidechain': False, 'type': 'assistant', 'cwd': project, 'timestamp': iso(ts + 60),
                      'sessionId': sid, 'message': {'role': 'assistant', 'content': [
                          {'type': 'text', 'text': reply if i == len(prompts) - 1 else 'Working on it.'}]}})
    lines.append({'type': 'ai-title', 'aiTitle': title, 'sessionId': sid})
    lines.append({'type': 'cost-state', 'totalCostUSD': cost, 'sessionId': sid})
    path = os.path.join(d, sid + '.jsonl')
    with open(path, 'w', encoding='utf-8') as fh:
        for line in lines:
            fh.write(dumps(line) + '\n')
    os.utime(path, (t0 + 3600, t0 + 3600))
    if live and sys.platform.startswith('linux'):
        sd = os.path.join(root, 'claude', 'sessions')
        os.makedirs(sd, exist_ok=True)
        with open('/proc/1/stat') as fh:
            start = fh.read().rsplit(')', 1)[1].split()[19]
        with open(os.path.join(sd, '1.json'), 'w', encoding='utf-8') as fh:
            json.dump({'pid': 1, 'procStart': start, 'sessionId': sid, 'cwd': project, 'status': 'idle'}, fh)
        os.utime(path, (now - 300, now - 300))
    return sid


def codex_session(root, project, prompts, reply, age_h, now=None):
    now = now or time.time()
    sid = str(uuid.uuid4())
    t0 = now - age_h * 3600
    d = os.path.join(root, 'codex', 'sessions', *time.strftime('%Y %m %d', time.gmtime(t0)).split())
    os.makedirs(d, exist_ok=True)
    stamp = time.strftime('%Y-%m-%dT%H-%M-%S', time.gmtime(t0))
    path = os.path.join(d, f'rollout-{stamp}-{sid}.jsonl')
    lines = [{'timestamp': iso(t0), 'type': 'session_meta', 'payload': {
        'id': sid, 'timestamp': iso(t0), 'cwd': project, 'git': {'branch': 'feature/cache'}}}]
    for i, p in enumerate(prompts):
        ts = t0 + i * 400
        lines.append({'timestamp': iso(ts), 'type': 'response_item', 'payload': {'type': 'message', 'role': 'user', 'content': [
            {'type': 'input_text', 'text': '<environment_context>\n<cwd>' + project + '</cwd>\n</environment_context>'}]}})
        lines.append({'timestamp': iso(ts), 'type': 'event_msg', 'payload': {'type': 'user_message', 'message': p, 'kind': 'plain'}})
        lines.append({'timestamp': iso(ts), 'type': 'response_item', 'payload': {
            'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': p}]}})
        lines.append({'timestamp': iso(ts + 90), 'type': 'event_msg', 'payload': {
            'type': 'agent_message', 'message': reply if i == len(prompts) - 1 else 'On it.'}})
    with open(path, 'w', encoding='utf-8') as fh:
        for line in lines:
            fh.write(dumps(line) + '\n')
    os.utime(path, (t0 + 1800, t0 + 1800))
    return sid


def hermes_db(root, rows, now=None):
    now = now or time.time()
    d = os.path.join(root, 'hermes')
    os.makedirs(d, exist_ok=True)
    con = sqlite3.connect(os.path.join(d, 'state.db'))
    con.execute('create table sessions (id text primary key, cwd text, git_branch text, title text, title_source text,'
                ' started_at real, ended_at real, last_activity_at real, message_count integer, estimated_cost_usd real,'
                ' archived integer)')
    con.execute('create table messages (id integer primary key autoincrement, session_id text, role text, content text,'
                ' active integer)')
    for sid, cwd, title, prompts, reply, age_h, ended in rows:
        t0 = now - age_h * 3600
        con.execute('insert into sessions values (?,?,?,?,?,?,?,?,?,?,0)',
                    (sid, cwd, None, title, 'llm', t0, t0 + 900 if ended else None, t0 + 900, len(prompts) * 2, 0.0))
        for i, p in enumerate(prompts):
            con.execute('insert into messages (session_id, role, content, active) values (?,?,?,1)', (sid, 'user', p))
            con.execute('insert into messages (session_id, role, content, active) values (?,?,?,1)',
                        (sid, 'assistant', reply if i == len(prompts) - 1 else 'Done, next?'))
    con.commit()
    con.close()


def build(root):
    """Create the full sample set; returns a dict of ids per agent."""
    ids = {'claude': [], 'codex': [], 'hermes': []}
    ids['claude'].append(claude_session(
        root, f'{HOME}/dev/rocket-api', 'Rate limiter returns 429 too early',
        ['the rate limiter is rejecting requests under the limit, find out why',
         'write a regression test for the window rollover', 'ok ship it and update the changelog'],
        'The window key used local time, so the bucket rolled over at the wrong second near midnight. '
        'Fixed in limiter.py with a UTC timestamp and added test_window_rollover.', 0.4, 1.84, live=True))
    ids['claude'].append(claude_session(
        root, f'{HOME}/dev/bakery-site', 'Astro build fails on image import',
        ['the astro build dies on the hero image import', 'can you also shrink the hero to under 200kb'],
        'The import path had a stale extension. Build passes and the hero is now 164 KB as WebP.', 5, 0.62))
    ids['claude'].append(claude_session(
        root, f'{HOME}/dotfiles', 'Fish prompt shows wrong git branch',
        ['my fish prompt shows the wrong branch after a worktree switch'],
        'The prompt cached the branch per shell. It now reads it on each prompt render.', 26, 0.21))
    ids['claude'].append(claude_session(
        root, f'{HOME}/dev/rocket-api', 'Postgres connection pool exhaustion',
        ['we keep running out of postgres connections in staging', 'add a metric for pool wait time'],
        'Background jobs opened a session per row. They now share one pool and a pool_wait_seconds histogram is exported.',
        50, 3.10))
    ids['claude'].append(claude_session(
        root, f'{HOME}/dev/ledger', 'CSV export misaligns columns',
        ['csv export has shifted columns when a memo contains a comma'],
        'Memos are now quoted through the csv module instead of joined by hand.', 80, 0.44))
    ids['codex'].append(codex_session(
        root, f'{HOME}/dev/rocket-api', ['add a redis cache in front of the pricing lookup', 'invalidate it when a price changes'],
        'Added a cache-aside layer keyed by sku with a 10 minute TTL and an invalidation hook on PriceUpdated.', 2))
    ids['codex'].append(codex_session(
        root, f'{HOME}/dev/bakery-site', ['migrate the contact form to server actions'],
        'The form now posts to a server action with zod validation. Removed the old API route.', 30))
    hermes_rows = [
        ('20261104_091500_a1b2c3', f'{HOME}/dev/ledger', 'Reconcile October statements',
         ['reconcile the october bank statements against ledger'],
         'All 212 transactions matched except two pending card holds, listed in reconcile_report.md.', 9, True),
        ('20261102_181200_d4e5f6', f'{HOME}/notes', 'Weekly planning notes', ['turn my voice memo into a weekly plan'],
         'Plan written to notes/week-45.md with three priorities and a Friday review slot.', 60, True),
    ]
    hermes_db(root, hermes_rows)
    ids['hermes'] = [r[0] for r in hermes_rows]
    return ids


if __name__ == '__main__':
    build(sys.argv[1])
    print(sys.argv[1])
