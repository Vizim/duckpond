import os

from duckpond import picker


def test_enter_resumes_and_new_rows_start_new():
    assert picker.decide('', 'codex', 'abc') == 'resume'
    assert picker.decide('', 'claude', '__NEW__') == 'new'
    assert picker.decide('', 'claude', '__CLOUD__') == 'cloud-link'


def test_claude_only_actions_fall_back_for_other_agents():
    assert picker.decide('ctrl-f', 'claude', 'abc') == 'fork'
    assert picker.decide('ctrl-f', 'hermes', 'abc') == 'resume'
    assert picker.decide('ctrl-t', 'claude', 'abc') == 'cloud'
    assert picker.decide('ctrl-t', 'codex', 'abc') == 'new'


def test_new_and_handoff_keys():
    assert picker.decide('ctrl-n', 'hermes', 'abc') == 'new'
    assert picker.decide('ctrl-f', 'codex', '__NEW__') == 'new'
    assert picker.decide('ctrl-o', 'claude', 'abc') == 'handoff'
    assert picker.decide('ctrl-o', 'claude', '__NEW__') == 'new'


def test_commands_substitute_session_id():
    cmd = [c.replace('{sid}', 'abc') for c in picker.COMMANDS['hermes']['resume']]
    assert cmd == ['hermes', '--resume', 'abc']
    cmd = [c.replace('{sid}', 'abc') for c in picker.COMMANDS['claude']['fork']]
    assert cmd == ['claude', '--resume', 'abc', '--fork-session']


def test_window_argv_custom_terminal():
    me = ['/x/duckpond']
    assert picker.window_argv(me, custom='alacritty -e') == ['alacritty', '-e', '/x/duckpond']
    assert picker.window_argv(me, custom='gnome-terminal -- {cmd}') == ['gnome-terminal', '--', '/x/duckpond']
    assert picker.window_argv(me, custom='wezterm start -- {cmd} --flag') == ['wezterm', 'start', '--', '/x/duckpond', '--flag']


def test_window_argv_defaults_per_platform():
    me = ['/x/duckpond']
    assert picker.window_argv(me, platform='darwin')[0] == 'osascript'
    assert picker.window_argv(me, platform='win32', which=lambda n: n == 'wt') == ['wt', '/x/duckpond']
    assert picker.window_argv(me, platform='win32', which=lambda n: False)[:3] == ['cmd', '/c', 'start']
    assert picker.window_argv(me, platform='linux', which=lambda n: n == 'kitty') == ['kitty', '-e', '/x/duckpond']
    assert picker.window_argv(me, platform='linux', which=lambda n: False) is None


def test_config_roundtrip(tmp_path, monkeypatch):
    from duckpond import config
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    monkeypatch.setenv('APPDATA', str(tmp_path))
    monkeypatch.delenv('DUCKPOND_TERMINAL', raising=False)
    monkeypatch.delenv('DUCKPOND_TERMINAL', raising=False)
    assert config.get('terminal') is None
    config.set_value('terminal', 'foot')
    assert config.get('terminal') == 'foot'
    monkeypatch.setenv('DUCKPOND_TERMINAL', 'kitty -e')
    assert config.get('terminal') == 'kitty -e'
    monkeypatch.delenv('DUCKPOND_TERMINAL')
    config.set_value('terminal', '')
    assert config.get('terminal') is None


def test_pond_frame_layout():
    from duckpond import pond
    from duckpond.duck import MID_ROWS, MINI_ROWS
    empty = pond.plain(pond.frame([], 60, 0))
    assert any('no sessions running' in line for line in empty)
    ducks = [('claude', 'Rate limiter returns 429'), ('codex', 'redis cache'), ('hermes', 'Reconcile October')]
    beak = MINI_ROWS[0].strip('\u2800')
    for t in (0, 1):
        lines = pond.plain(pond.frame(ducks, 90, t))
        assert sum(line.count(beak) for line in lines) == 3
        assert all(len(line) <= 90 for line in lines)
        assert 'claude' in lines[-2] and 'hermes' in lines[-2]
        assert 'redis cache' in lines[-1] and 'Reconcile October' in lines[-1]
        assert sum(1 for line in lines if '\u2800' in line or '⠉' in line) >= 2
    wide = pond.plain(pond.frame(ducks[:1], 120, 0))
    assert any(MID_ROWS[0].strip('\u2800') in line for line in wide)


def test_header_and_mini_duck():
    import re
    from duckpond import duck
    assert len(duck.MINI_ROWS) == 4 and len({len(r) for r in duck.MINI_ROWS}) == 1
    rows = ['claude\t__NEW__\t/h\t+ new claude session', 'claude\tabc\t/h\tx', 'codex\tdef\t/h\ty']
    text = re.sub(r'\x1b\[[0-9;]*m', '', picker.header(rows))
    assert 'duckpond' in text and 'all your AI sessions, one pond' in text
    assert '2 sessions from claude, codex' in text and 'Hit ?' in text
    assert 'no sessions yet' in picker.header(rows[:1])


def test_guide_mentions_every_key_in_the_header():
    import re
    from duckpond import help as guide
    text = guide.guide(color=False)
    for key in ('Enter', 'Ctrl-O', 'Ctrl-F', 'Ctrl-N', 'Ctrl-T', 'Ctrl-P', 'Ctrl-X', 'Ctrl-U', 'Ctrl-Y', 'Ctrl-R', '?', 'F1'):
        assert key in text
    assert 'duckpond pond' in text and '~/.cache/duckpond' in text
    assert not re.search(r'\x1b', text)


def test_install_skills_into_agent_homes(stores, capsys):
    import importlib
    from duckpond import skills
    importlib.reload(skills)
    out = skills.install()
    for agent, home in (('claude', 'CLAUDE_CONFIG_DIR'), ('codex', 'CODEX_HOME'), ('hermes', 'HERMES_HOME')):
        path = os.path.join(os.environ[home], 'skills', 'duckpond', 'SKILL.md')
        assert os.path.isfile(path), agent
        text = open(path, encoding='utf-8').read()
        assert text.startswith('---\nname: duckpond\n') and 'handoff-' in text and 'duckpond list --json' in text
    assert 'claude' in out and 'hermes' in out
    assert skills.uninstall().startswith('removed')
    assert not os.path.exists(os.path.join(os.environ['CODEX_HOME'], 'skills', 'duckpond'))


def test_doctor_ends_with_a_verdict(stores, capsys):
    import pytest
    s = stores['sessions']
    with pytest.raises(SystemExit):
        s.main(['doctor'])
    out = capsys.readouterr().out
    assert 'ready' in out or 'install fzf' in out or 'no agents found' in out


def test_watch_signature_ignores_the_clock():
    a = ['claude\tabc\t/h\t\x1b[32m●\x1b[0m \x1b[2m11-05 15:03\x1b[0m  claude  proj  Title']
    b = ['claude\tabc\t/h\t\x1b[32m●\x1b[0m \x1b[2m11-05 15:09\x1b[0m  claude  proj  Title']
    c = ['claude\tabc\t/h\t  \x1b[2m11-05 15:09\x1b[0m  claude  proj  Title']
    d = ['claude\tabc\t/h\t\x1b[32m●\x1b[0m \x1b[2m11-05 15:09\x1b[0m  claude  proj  Renamed']
    assert picker.signature(a) == picker.signature(b)
    assert picker.signature(a) != picker.signature(c)
    assert picker.signature(a) != picker.signature(d)


def test_hints_name_a_way_to_install(monkeypatch):
    from duckpond import hints
    monkeypatch.setattr(hints.shutil, 'which', lambda n: '/usr/bin/apt' if n == 'apt' else None)
    assert hints.fzf_hint() == 'fzf is missing. install it with: sudo apt install fzf'
    monkeypatch.setattr(hints.shutil, 'which', lambda n: None)
    assert 'github.com/junegunn/fzf/releases' in hints.fzf_hint()
    assert 'npm install -g @openai/codex' in hints.agent_hint('codex')
    assert 'Claude Code' in hints.no_agents_hint() and 'Hermes' in hints.no_agents_hint()
