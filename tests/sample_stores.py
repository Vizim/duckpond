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
        usage = {'input_tokens': 20, 'cache_creation_input_tokens': 300, 'cache_read_input_tokens': 5000,
                 'cache_creation': {'ephemeral_5m_input_tokens': 300, 'ephemeral_1h_input_tokens': 0}, 'output_tokens': 400}
        lines.append({'parentUuid': None, 'isSidechain': False, 'type': 'assistant', 'cwd': project, 'timestamp': iso(ts + 60),
                      'sessionId': sid, 'message': {'id': f'msg_{i}', 'role': 'assistant', 'usage': usage, 'content': [
                          {'type': 'text', 'text': reply if i == len(prompts) - 1 else 'Working on it.'}]}})
        lines.append({'parentUuid': None, 'isSidechain': False, 'type': 'assistant', 'cwd': project, 'timestamp': iso(ts + 61),
                      'sessionId': sid, 'message': {'id': f'msg_{i}', 'role': 'assistant', 'usage': usage, 'content': [
                          {'type': 'tool_use', 'id': f'toolu_r{i}', 'name': 'Read', 'input': {'file_path': '/x/y.py'}}]}})
    if live:
        lines.append({'parentUuid': None, 'isSidechain': False, 'type': 'assistant', 'cwd': project, 'timestamp': iso(ts + 90),
                      'sessionId': sid, 'message': {'role': 'assistant', 'content': [
                          {'type': 'tool_use', 'id': 'toolu_0', 'name': 'Agent',
                           'input': {'description': 'Review the diff', 'prompt': 'Review it.'}},
                          {'type': 'tool_use', 'id': 'toolu_9', 'name': 'Agent',
                           'input': {'description': 'Finished already', 'prompt': 'Done.'}},
                          {'type': 'tool_use', 'id': 'toolu_bg', 'name': 'Agent',
                           'input': {'description': 'Background review', 'prompt': 'Review.'}},
                          {'type': 'tool_use', 'id': 'toolu_bg2', 'name': 'Agent',
                           'input': {'description': 'Background done', 'prompt': 'Review.'}},
                          {'type': 'tool_use', 'id': 'toolu_1', 'name': 'Bash',
                           'input': {'command': 'pytest -q', 'description': 'Run the test suite'}}]}})
        lines.append({'parentUuid': None, 'isSidechain': False, 'type': 'user', 'cwd': project, 'timestamp': iso(ts + 120),
                      'sessionId': sid, 'message': {'role': 'user', 'content': [
                          {'type': 'tool_result', 'tool_use_id': 'toolu_9', 'content': 'ok'},
                          {'type': 'tool_result', 'tool_use_id': 'toolu_bg', 'content': [{'type': 'text', 'text': 'Async agent launched successfully. agentId: x'}]},
                          {'type': 'tool_result', 'tool_use_id': 'toolu_bg2', 'content': [{'type': 'text', 'text': 'Async agent launched successfully. agentId: y'}]}]}})
        lines.append({'type': 'queue-operation', 'operation': 'enqueue', 'timestamp': iso(ts + 150), 'sessionId': sid,
                      'content': '<task-notification>\n<tool-use-id>toolu_bg2</tool-use-id>\n<status>completed</status>\n</task-notification>'})
        lines.append({'type': 'queue-operation', 'operation': 'enqueue', 'timestamp': iso(ts + 160), 'sessionId': sid,
                      'content': 'also make the tests faster'})
        lines.append({'type': 'queue-operation', 'operation': 'remove', 'timestamp': iso(ts + 161), 'sessionId': sid,
                      'content': 'also make the tests faster'})
        lines.append({'parentUuid': None, 'isSidechain': False, 'type': 'user', 'cwd': project, 'timestamp': iso(ts + 170),
                      'sessionId': sid, 'message': {'role': 'user', 'content': 'Another Claude session sent a message:\n<agent-message>hi</agent-message>'}})
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
        os.utime(path, (now - 3, now - 3))
    return sid


def codex_session(root, project, prompts, reply, age_h, now=None, live=False):
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
        lines.append({'timestamp': iso(ts + 60), 'type': 'response_item', 'payload': {
            'type': 'function_call', 'name': 'shell', 'call_id': 'c1',
            'arguments': '{"command":["bash","-lc","redis-cli ping"]}'}})
        lines.append({'timestamp': iso(ts + 90), 'type': 'event_msg', 'payload': {
            'type': 'agent_message', 'message': reply if i == len(prompts) - 1 else 'On it.'}})
        lines.append({'timestamp': iso(ts + 91), 'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
            'total_token_usage': {'input_tokens': 9000, 'output_tokens': 900},
            'last_token_usage': {'input_tokens': 3000, 'cached_input_tokens': 2500, 'output_tokens': 150}}}})
    with open(path, 'w', encoding='utf-8') as fh:
        for line in lines:
            fh.write(dumps(line) + '\n')
    stamp = now - 10 if live else t0 + 1800
    os.utime(path, (stamp, stamp))
    return sid


def hermes_db(root, rows, now=None):
    now = now or time.time()
    d = os.path.join(root, 'hermes')
    os.makedirs(d, exist_ok=True)
    con = sqlite3.connect(os.path.join(d, 'state.db'))
    con.execute('create table sessions (id text primary key, cwd text, git_branch text, title text, title_source text,'
                ' started_at real, ended_at real, last_activity_at real, message_count integer, estimated_cost_usd real,'
                ' archived integer, parent_session_id text, input_tokens integer, output_tokens integer, cache_read_tokens integer,'
                ' api_call_count integer, cache_write_tokens integer, reasoning_tokens integer)')
    con.execute('create table messages (id integer primary key autoincrement, session_id text, role text, content text,'
                ' timestamp real, token_count integer, tool_name text, active integer)')
    for sid, cwd, title, prompts, reply, age_h, ended in rows:
        t0 = now - age_h * 3600
        last = now - 8 if not ended else t0 + 900
        con.execute('insert into sessions (id, cwd, git_branch, title, title_source, started_at, ended_at, last_activity_at,'
                    ' message_count, estimated_cost_usd, archived, input_tokens, output_tokens, cache_read_tokens, api_call_count,'
                    ' cache_write_tokens, reasoning_tokens) values (?,?,?,?,?,?,?,?,?,?,0,?,?,?,?,?,?)',
                    (sid, cwd, None, title, 'llm', t0, None if not ended else t0 + 900, last, len(prompts) * 2, 0.0,
                     3000 * len(prompts), 500 * len(prompts), 1000 * len(prompts), len(prompts), 200 * len(prompts), 50 * len(prompts)))
        for i, p in enumerate(prompts):
            con.execute('insert into messages (session_id, role, content, timestamp, active) values (?,?,?,?,1)',
                        (sid, 'user', p, t0 + i * 300))
            con.execute('insert into messages (session_id, role, content, timestamp, active) values (?,?,?,?,1)',
                        (sid, 'assistant', reply if i == len(prompts) - 1 else 'Done, next?', t0 + i * 300 + 60))
        if not ended:
            con.execute('insert into messages (session_id, role, content, timestamp, tool_name, active) values (?,?,?,?,?,1)',
                        (sid, 'tool', '{"ok": true}', now - 9, 'terminal'))
            for j, task in enumerate(('count the lines in words.txt', 'list the files here')):
                cid = f'{sid}_child{j}'
                con.execute('insert into sessions (id, cwd, title, title_source, started_at, ended_at, last_activity_at,'
                            ' message_count, estimated_cost_usd, archived, parent_session_id, input_tokens, output_tokens, cache_read_tokens)'
                            ' values (?,?,?,?,?,?,?,?,?,0,?,?,?,?)',
                            (cid, cwd, None, 'llm', now - 6, None if j == 0 else now - 2, now - 5, 2, 0.0, sid, 900, 40, 0))
                con.execute('insert into messages (session_id, role, content, timestamp, active) values (?,?,?,?,1)',
                            (cid, 'user', task, now - 6))
    con.commit()
    con.close()


def copilot_session(root, project, prompts, reply, age_h, now=None, live=False):
    now = now or time.time()
    sid = str(uuid.uuid4())
    d = os.path.join(root, 'copilot', 'session-state', sid)
    os.makedirs(d, exist_ok=True)
    t0 = now - age_h * 3600
    lines = [{'type': 'session.start', 'timestamp': iso(t0), 'data': {
        'sessionId': sid, 'startTime': iso(t0), 'selectedModel': 'gpt-5', 'context': {'cwd': project}}}]
    for i, p in enumerate(prompts):
        ts = t0 + i * 400
        lines.append({'type': 'user.message', 'timestamp': iso(ts), 'data': {'content': p}})
        lines.append({'type': 'assistant.turn_start', 'timestamp': iso(ts + 1), 'data': {}})
        lines.append({'type': 'assistant.message', 'timestamp': iso(ts + 30), 'data': {
            'content': '', 'toolRequests': [{'toolCallId': f't{i}', 'name': 'bash', 'arguments': {'command': 'npm test'}}]}})
        lines.append({'type': 'tool.execution_complete', 'timestamp': iso(ts + 40), 'data': {'toolCallId': f't{i}', 'toolName': 'bash', 'result': 'ok'}})
        lines.append({'type': 'assistant.message', 'timestamp': iso(ts + 60), 'data': {
            'content': reply if i == len(prompts) - 1 else 'Looking.', 'toolRequests': []}})
        if not (live and i == len(prompts) - 1):
            lines.append({'type': 'assistant.turn_end', 'timestamp': iso(ts + 61), 'data': {}})
    path = os.path.join(d, 'events.jsonl')
    with open(path, 'w', encoding='utf-8') as fh:
        for line in lines:
            fh.write(dumps(line) + '\n')
    stamp = now - 8 if live else t0 + 1800
    os.utime(path, (stamp, stamp))
    return sid


def vscode_session(root, project, title, prompts, reply, age_h, now=None):
    now = now or time.time()
    sid = str(uuid.uuid4())
    ws = os.path.join(root, 'vscode', 'workspaceStorage', uuid.uuid4().hex)
    os.makedirs(os.path.join(ws, 'chatSessions'), exist_ok=True)
    with open(os.path.join(ws, 'workspace.json'), 'w', encoding='utf-8') as fh:
        fh.write(dumps({'folder': 'file://' + project}))
    t0 = now - age_h * 3600
    def request(i, p, done=True):
        ts = int((t0 + i * 500) * 1000)
        parts = [{'kind': 'markdownContent', 'content': {'value': reply if i == len(prompts) - 1 else 'On it.'}}]
        r = {'requestId': f'request_{i}', 'message': {'text': p, 'parts': []}, 'timestamp': ts, 'modelId': 'gpt-5',
             'response': parts, 'variableData': {'variables': []}}
        if done:
            r['result'] = {'metadata': {}}
        return r
    lines = [{'kind': 0, 'v': {'version': 3, 'creationDate': int(t0 * 1000), 'sessionId': sid, 'customTitle': None,
                               'responderUsername': 'GitHub Copilot', 'requests': [request(0, prompts[0])],
                               'pendingRequests': [], 'inputState': {}}}]
    for i, p in enumerate(prompts[1:], 1):
        lines.append({'kind': 2, 'k': ['requests'], 'v': [request(i, p, done=False)]})
        lines.append({'kind': 2, 'k': ['requests', i, 'response'], 'v': [{'kind': 'toolInvocationSerialized', 'toolId': 'runInTerminal'}]})
        lines.append({'kind': 1, 'k': ['requests', i, 'promptTokens'], 'v': 20000})
        lines.append({'kind': 1, 'k': ['requests', i, 'completionTokens'], 'v': 800})
        lines.append({'kind': 1, 'k': ['requests', i, 'promptTokens'], 'v': 26000})
        lines.append({'kind': 1, 'k': ['requests', i, 'completionTokens'], 'v': 1500})
        lines.append({'kind': 1, 'k': ['requests', i, 'result'], 'v': {'metadata': {}}})
    if title:
        lines.append({'kind': 1, 'k': ['customTitle'], 'v': title})
    path = os.path.join(ws, 'chatSessions', sid + '.jsonl')
    with open(path, 'w', encoding='utf-8') as fh:
        for line in lines:
            fh.write(dumps(line) + '\n')
    import base64
    con = sqlite3.connect(os.path.join(ws, 'state.vscdb'))
    con.execute('create table ItemTable (key text unique on conflict replace, value blob)')
    shown = base64.b64encode(sid.encode()).decode()
    con.execute('insert into ItemTable values (?, ?)', ('memento/interactive-session-view-copilot',
                dumps({'sessionResource': {'external': f'vscode-chat-session://local/{shown}'}})))
    con.commit()
    con.close()
    stamp = now - 30 if age_h < 1 else t0 + 1200
    os.utime(path, (stamp, stamp))
    return sid


def build(root):
    """Create the full sample set; returns a dict of ids per agent."""
    ids = {'claude': [], 'codex': [], 'hermes': [], 'copilot': [], 'vscode': []}
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
        'Added a cache-aside layer keyed by sku with a 10 minute TTL and an invalidation hook on PriceUpdated.', 2, live=True))
    ids['codex'].append(codex_session(
        root, f'{HOME}/dev/bakery-site', ['migrate the contact form to server actions'],
        'The form now posts to a server action with zod validation. Removed the old API route.', 30))
    ids['copilot'].append(copilot_session(
        root, f'{HOME}/dev/rocket-api', ['why does the deploy script skip the migrations step'],
        'The step is gated on CI=true, which the deploy runner never sets.', 1.5, live=True))
    ids['vscode'].append(vscode_session(
        root, f'{HOME}/dev/bakery-site', 'Contact form validation',
        ['the contact form accepts an empty email', 'add a test for it'],
        'Added an email check and a unit test in contact.test.ts.', 0.2))
    hermes_rows = [
        ('20261105_224941_dd3d02', f'{HOME}/dev/ledger', 'Check the ledger exports',
         ['use subagents to count lines in words.txt and list the files'], 'Both subagents are running.', 0.1, False),
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
