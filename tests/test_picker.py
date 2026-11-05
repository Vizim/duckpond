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
    empty = pond.plain(pond.frame([], 60, 0))
    assert any('no ducks' in line for line in empty)
    ducks = [('claude', 'Rate limiter returns 429'), ('codex', 'redis cache'), ('hermes', 'Reconcile October')]
    for t in (0, 1):
        lines = pond.plain(pond.frame(ducks, 80, t))
        assert sum(line.count('<(o )___') for line in lines) == 3
        assert all(len(line) <= 80 for line in lines)
        assert 'redis cache' in lines[-1] and 'Reconcile October' in lines[-1]


def test_header_and_mini_duck():
    import re
    from duckpond import duck
    assert len(duck.MINI_ROWS) == 4 and len({len(r) for r in duck.MINI_ROWS}) == 1
    rows = ['claude\t__NEW__\t/h\t+ new claude session', 'claude\tabc\t/h\tx', 'codex\tdef\t/h\ty']
    text = re.sub(r'\x1b\[[0-9;]*m', '', picker.header(rows))
    assert 'duckpond' in text and 'all your AI sessions, one pond' in text
    assert '2 sessions on the pond from claude, codex' in text
    assert 'the pond is empty' in picker.header(rows[:1])


def test_guide_mentions_every_key_in_the_header():
    import re
    from duckpond import help as guide
    text = guide.guide(color=False)
    for key in ('Enter', 'Ctrl-O', 'Ctrl-F', 'Ctrl-N', 'Ctrl-T', 'Ctrl-P', 'Ctrl-X', 'Ctrl-U', 'Ctrl-Y', 'Ctrl-R', 'F1'):
        assert key in text
    assert 'duckpond pond' in text and '~/.cache/duckpond' in text
    assert not re.search(r'\x1b', text)
