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
