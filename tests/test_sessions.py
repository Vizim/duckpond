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
    assert agents.count('claude') == 5 and agents.count('codex') == 2 and agents.count('hermes') == 2
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
    for agent in ('claude', 'codex', 'hermes'):
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
    assert len(rows) == 9
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
    assert 'sessions   9 listed' in out and 'cache' in out
