import subprocess
import time
import json
import os
import re
import stat
import sys

import pytest

ANSI = re.compile(r'\x1b\[[0-9;]*m')


def listing(sessions, capsys, *args):
    sessions.main(['list', *args])
    out = capsys.readouterr().out
    return [ANSI.sub('', line).split('\t') for line in out.splitlines() if line]


def test_lists_every_agent_newest_first(stores, capsys):
    rows = [r for r in listing(stores['sessions'], capsys) if not r[1].startswith('__')]
    agents = [r[0] for r in rows]
    assert agents.count('claude') == 5 and agents.count('codex') == 2 and agents.count('hermes') == 3
    assert agents.count('copilot') == 1 and agents.count('vscode') == 1
    assert agents[0] == 'claude' and 'Rate limiter' in rows[0][3]
    assert rows[0][2] == '/home/ada/dev/rocket-api'


def test_search_matches_agent_title_and_prompts(stores, capsys):
    s = stores['sessions']
    assert {r[0] for r in listing(s, capsys, 'hermes')} == {'hermes'}
    rows = listing(s, capsys, 'redis', 'pricing')
    assert len(rows) == 1 and rows[0][0] == 'codex'
    assert listing(s, capsys, 'no', 'such', 'thing') == []


def test_codex_dedupes_prompts_and_skips_injected_context(stores, capsys):
    s = stores['sessions']
    sid = stores['ids']['codex'][0]
    listing(s, capsys)
    s.main(['preview', 'codex', sid])
    text = ANSI.sub('', capsys.readouterr().out)
    assert text.count('add a redis cache') == 2  # title and the prompt list
    assert '<environment_context>' not in text and 'prompts    2' in text


def test_incremental_scan_equals_full_scan(stores, tmp_path):
    s = stores['sessions']
    for agent, path in s.transcript_files():
        data = open(path, 'rb').read()
        full, _ = s.scan(path, s.FEEDS[agent], s.new_state(), 0)
        part = tmp_path / 'part.jsonl'
        part.write_bytes(data[:len(data) // 2])
        state, pos = s.scan(str(part), s.FEEDS[agent], s.new_state(), 0)
        part.write_bytes(data)
        state, pos = s.scan(str(part), s.FEEDS[agent], state, pos)
        assert state == full and pos == len(data)


def test_cache_is_reused_and_only_new_bytes_are_read(stores, capsys, monkeypatch):
    s = stores['sessions']
    listing(s, capsys)
    index = s.load_json(s.INDEX, {})
    path = next(p for p, e in index.items() if e['agent'] == 'claude')
    before = index[path]['pos']
    with open(path, 'ab') as fh:
        fh.write(b'{"type":"ai-title","aiTitle":"Renamed by test","sessionId":"x"}\n')
    rows = listing(s, capsys)
    assert any('Renamed by test' in r[3] for r in rows)
    assert s.load_json(s.INDEX, {})[path]['pos'] > before


def test_hide_and_unhide(stores, capsys):
    s = stores['sessions']
    sid = stores['ids']['hermes'][0]
    s.main(['hide', 'hermes', sid])
    assert sid not in [r[1] for r in listing(s, capsys)]
    s.main(['unhide-all'])
    assert sid in [r[1] for r in listing(s, capsys)]


def test_export_markdown_has_turns(stores, tmp_path, capsys):
    s = stores['sessions']
    listing(s, capsys)
    for agent in ('claude', 'codex', 'hermes', 'copilot', 'vscode'):
        out = tmp_path / f'{agent}.md'
        s.main(['export', agent, stores['ids'][agent][0], str(out)])
        text = out.read_text(encoding='utf-8')
        assert text.startswith(f'# Handoff from a {agent} session')
        assert '**You:**' in text and f'**{agent}:**' in text


def test_bad_ids_are_rejected(stores):
    s = stores['sessions']
    with pytest.raises(SystemExit):
        s.main(['preview', 'claude', '../../etc/passwd'])
    with pytest.raises(SystemExit):
        s.main(['hide', 'claude;rm', 'x'])


def test_json_output(stores, capsys):
    s = stores['sessions']
    s.main(['list', '--json'])
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 12
    assert {'agent', 'id', 'dir', 'title', 'last_active', 'prompts'} <= set(rows[0])


@pytest.mark.skipif(sys.platform == 'win32', reason='posix permissions')
def test_cache_is_private(stores, capsys):
    s = stores['sessions']
    listing(s, capsys)
    assert stat.S_IMODE(os.stat(stores['cache']).st_mode) == 0o700
    for f in os.listdir(stores['cache']):
        assert stat.S_IMODE(os.stat(os.path.join(stores['cache'], f)).st_mode) == 0o600


def test_own_pid_counts_as_live(stores):
    s = stores['sessions']
    lock = dict(pid=os.getpid(), sessionId='me', cwd='/')
    if sys.platform.startswith('linux'):
        lock['procStart'] = s.proc_start(os.getpid())
    assert s.session_alive(lock)
    assert not s.session_alive(dict(pid=2 ** 22 - 1, sessionId='x'))


def test_store_name_matches_claude_encoding(stores):
    s = stores['sessions']
    assert s.store_name('/home/ada/.claude/IDR_October') == '-home-ada--claude-IDR-October'
    assert s.store_name('C:\\Users\\ada\\proj') == 'C--Users-ada-proj'


def test_doctor_runs(stores, capsys):
    s = stores['sessions']
    with pytest.raises(SystemExit):
        s.main(['doctor'])
    out = capsys.readouterr().out
    assert 'sessions   12 listed' in out and 'cache' in out


def test_typed_cd_moves_the_resume_directory(stores, capsys):
    s = stores['sessions']
    listing(s, capsys)
    index = s.load_json(s.INDEX, {})
    path = next(p for p, e in index.items() if e['agent'] == 'claude' and e['sid'] == stores['ids']['claude'][0])
    line = {'type': 'user', 'cwd': '/home/ada/dev/rocket-api/services', 'isSidechain': False,
            'message': {'role': 'user', 'content': '<bash-input>cd services</bash-input>'}}
    with open(path, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(line, separators=(',', ':')) + '\n')
    rows = listing(s, capsys)
    row = next(r for r in rows if r[1] == stores['ids']['claude'][0])
    assert row[2] == '/home/ada/dev/rocket-api/services'


def test_tool_tracking_and_newest(stores):
    from duckpond import sessions
    everything = list(sessions.collect().values())
    assert all(e['data']['tool'] == 'Read y.py' for e in everything if e['agent'] == 'claude' and not e['data']['subagents'])
    live = [e for e in everything if e['agent'] == 'claude' and e['data']['subagents']]
    assert live and live[0]['data']['tool'] == 'Bash Run the test suite'
    assert live[0]['data']['prompts'][-1] == 'also make the tests faster' and live[0]['data']['turns'] == len(live[0]['data']['times'])
    subs = live[0]['data']['subagents']
    assert list(subs) == ['toolu_0', 'toolu_bg'] and subs['toolu_0'][0] == 'Review the diff'
    assert live[0]['data']['times'] and all(isinstance(t, int) for t in live[0]['data']['times'])
    codex = [e for e in sessions.collect().values() if e['agent'] == 'codex']
    assert codex and all(e['data']['tool'] == 'shell bash -lc redis-cli ping' for e in codex)
    for e in sessions.collect().values():
        if e['agent'] == 'copilot':
            assert e['data']['tok'] == []
            continue
        if e['agent'] == 'vscode':
            continue
        tok = e['data']['tok']
        assert tok and all(len(m) == 4 for m in tok)
        if e['agent'] == 'claude':
            replies = e['data']['turns'] - (1 if e['data']['subagents'] else 0)
            assert sum(m[2] for m in tok) == 400 * replies and tok[0][1:] == [5320, 400, 5000]
        elif e['agent'] == 'codex':
            assert all(m[1:] == [3000, 150, 2500] for m in tok) and e['data']['tool'] == 'shell bash -lc redis-cli ping'
        else:
            n = e['data']['turns']
            assert tok[0][1:] == [4200 * n, 550 * n, 1000 * n]
    s = sessions.new_state()
    sessions.claude_feed(s, '{"type":"assistant","isSidechain":false,"message":{"id":"msg_x","usage":{"input_tokens":"n/a"},'
                            '"content":[{"type":"tool_use","id":"","name":"Agent","input":{}},'
                            '{"type":"tool_use","id":"toolu_r","name":"Read","input":{"file_path":"/a/b.py"}},'
                            '{"type":"tool_use","id":"toolu_b","name":"Bash","input":{"command":"ls","description":"List"}}]},'
                            '"timestamp":"2026-11-05T10:00:00Z"}', 'store')
    assert s['subagents'] == {} and s['tool'] == 'Bash List' and s['tok'] == []
    sessions.claude_feed(s, '{"type":"assistant","isSidechain":false,"message":{"id":"msg_y","usage":{"input_tokens":4,'
                            '"cache_creation":{"ephemeral_5m_input_tokens":1},"output_tokens":900},"content":[{"type":"tool_use","id":"toolu_a",'
                            '"name":"Agent","input":{"description":"Old one"}}]},"timestamp":"2026-11-05T10:00:00Z"}', 'store')
    assert s['tok'][0][2] == 900 and s['subagents']['toolu_a'] == ['Old one', int(sessions.to_epoch('2026-11-05T10:00:00Z'))]
    sessions.claude_feed(s, '{"type":"attachment","content":"<task-notification><tool-use-id>toolu_a</tool-use-id></task-notification>"}', 'store')
    assert s['subagents'] == {}
    sessions.codex_feed(s, '{"type":"event_msg","timestamp":"2026-11-05T10:01:00Z","payload":{"type":"token_count","info":{"last_token_usage":{"input_tokens":"n/a","output_tokens":5}}}}', 'store')
    assert s['tok'][-1][1:] == [0, 5, 0]
    row = sessions.newest([])
    assert row and row[1] in sessions.AGENTS
    assert sessions.newest(['no-such-session-anywhere']) is None


def test_codex_and_hermes_status_from_activity(stores):
    from duckpond import sessions
    rows, _ = sessions.session_rows([], sessions.live_claude(), set())
    by_agent = {}
    for _, agent, sid, where, d, status in rows:
        by_agent.setdefault(agent, []).append(status)
    assert 'busy' in by_agent['codex'] and by_agent['codex'].count(None) == 1
    assert by_agent['hermes'] == ['busy', None, None]
    live = [d for _, agent, sid, where, d, status in rows if agent == 'hermes' and status]
    assert [v[0] for v in live[0]['subagents'].values()] == ['count the lines in words.txt']
    assert live[0]['tool'] == 'terminal' and live[0]['tok'] == [[live[0]['tok'][0][0], 4200, 550, 1000]] and live[0]['ctx'] == 4200


def test_copilot_and_vscode_backends(stores, monkeypatch):
    from duckpond import sessions
    monkeypatch.setattr(sessions, 'vscode_open_workspaces', lambda: set())
    rows, _ = sessions.session_rows([], sessions.live_claude(), set())
    cop = [(d, status, where) for _, agent, sid, where, d, status in rows if agent == 'copilot']
    vs = [(d, status, where) for _, agent, sid, where, d, status in rows if agent == 'vscode']
    assert len(cop) == 1 and len(vs) == 1
    d, status, where = cop[0]
    assert status == 'busy' and d['busy'] and where == '/home/ada/dev/rocket-api' and d['tool'] == 'bash npm test'
    assert d['prompts'] == ['why does the deploy script skip the migrations step'] and d['reply'].startswith('The step is gated')
    d, status, where = vs[0]
    assert status is None and where == os.path.normpath('/home/ada/dev/bakery-site') and sessions.title(d) == 'Contact form validation'
    monkeypatch.setattr(sessions, 'vscode_open_workspaces', lambda: {'bakery-site'})
    rows, _ = sessions.session_rows([], sessions.live_claude(), set())
    assert [status for _, agent, sid, where, dd, status in rows if agent == 'vscode'] == ['open']
    assert sessions.vscode_shown_chat(d['ws']) == stores['ids']['vscode'][0]
    monkeypatch.setattr(sessions, 'vscode_shown_chat', lambda ws: 'some-other-chat')
    rows, _ = sessions.session_rows([], sessions.live_claude(), set())
    assert [status for _, agent, sid, where, dd, status in rows if agent == 'vscode'] == [None]
    assert d['turns'] == 2 and d['tool'] == 'runInTerminal' and d['busy'] is False and d['reply'].startswith('Added an email check')
    assert d['times'] and all(t > 1_600_000_000 for t in d['times'])
    assert sum(m[1] for m in d['tok']) == 26000 and sum(m[2] for m in d['tok']) == 1500 and d['ctx'] == 26000


def test_vscode_open_folders(stores, monkeypatch):
    from duckpond import sessions
    import json
    text = ("CPU: x\nWorkspace Stats: \n|  Window (● README.md - duckpond - Visual Studio Code)\n|    Folder (duckpond): 118 files\n"
            "|      File types: py(34)\n|  Window (bakery site - Visual Studio Code)\n|    Folder (bakery site): 3 files\n")
    assert sessions.parse_vscode_status(text) == (2, {'duckpond', 'bakery site'})
    assert sessions.parse_vscode_status('nothing') == (0, set())
    monkeypatch.setattr(sessions, 'pid_any', lambda name: True)
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: None)
    sessions.save_json(sessions.VSCODE_WINDOWS, dict(at=time.time(), windows=1, names=['bakery-site']))
    assert sessions.vscode_open_folders() == {'bakery-site'}
    sessions.save_json(sessions.VSCODE_WINDOWS, dict(at=time.time() - 3600, windows=1, names=['bakery-site']))
    assert sessions.vscode_open_folders() == set()
    monkeypatch.setattr(sessions, 'pid_any', lambda name: False)
    assert sessions.vscode_open_folders() == set()


def test_hide_all_and_rebuild(stores, capsys):
    from duckpond import sessions
    s = stores['sessions']
    s.main(['hide-all'])
    rows = [r for r in listing(s, capsys) if not r[1].startswith('__')]
    assert rows == []
    s.main(['unhide-all'])
    assert len([r for r in listing(s, capsys) if not r[1].startswith('__')]) == 12
    assert os.path.exists(sessions.INDEX)
    s.main(['rebuild'])
    assert not os.path.exists(sessions.INDEX)
    assert len([r for r in listing(s, capsys) if not r[1].startswith('__')]) == 12


def test_ask_runs_only_on_yes(stores, monkeypatch, capsys):
    import io
    from duckpond import cli, sessions
    answers = iter(['n\n', 'y\n'])
    monkeypatch.setattr(cli, 'terminal', lambda: (io.StringIO(), io.StringIO(next(answers))))
    cli.ask('hide?', ['hide-all'])
    assert len([r for r in listing(stores['sessions'], capsys) if not r[1].startswith('__')]) == 12
    cli.ask('hide?', ['hide-all'])
    assert [r for r in listing(stores['sessions'], capsys) if not r[1].startswith('__')] == []
