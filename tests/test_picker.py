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
    from duckpond.duck import MINI_ROWS
    empty = pond.plain(pond.frame([], 60, 0))
    assert any('no sessions running' in line for line in empty)
    ducks = pond.demo_ducks()
    beak = '⣤⣤⣤'
    assert beak in MINI_ROWS[-1] and beak in pond.mirror(MINI_ROWS)[-1]
    for t in range(4):
        lines = pond.plain(pond.frame(ducks, 90, t))
        assert sum(line.count(beak) for line in lines) == 3
        assert all(len(line) <= 90 for line in lines)
        text = '\n'.join(lines)
        assert 'claude' in text and 'hermes' in text and 'busy' in text and 'idle 10m' in text
        assert 'redis cache for pricing' in text and 'Reconcile October' in text
        assert sum(1 for line in lines if '\u2800' in line or '⠉' in line) >= 2
    wide = pond.plain(pond.frame(ducks[:1], 120, 0))
    assert sum(line.count(beak) for line in wide) == 1
    assert all(len(line) <= 58 for line in wide if '⠉' not in line and '⣀' not in line)
    text = '\n'.join(pond.plain(pond.frame(ducks, 130, 0)))
    assert '~/code/api fix/limiter' in text and '34 prompts' in text and '$4.20' in text
    assert 'the burst window is still off by one,' in text and 'check the token refill math' in text
    narrow = pond.plain(pond.frame(ducks, 60, 0))
    assert sum(line.count(beak) for line in narrow) == 3 and all(len(line) <= 60 for line in narrow)
    head = pond.plain([pond.header(ducks, 80)])[0]
    assert head.startswith('duckpond  3 sessions running  2 busy 1 idle') and len(head) <= 80


def test_pond_time_helpers_and_source_guard(tmp_path, monkeypatch):
    from duckpond import pond
    assert pond.ago(5) == '5s' and pond.ago(90) == '1m' and pond.ago(7200) == '2h'
    assert pond.ago(3660) == '1h 1m' and pond.ago(200000) == '2d'
    assert pond.to_epoch(1793940309608) == 1793940309.608 and pond.to_epoch(12.5) == 12.5
    import calendar
    assert pond.to_epoch('2026-11-05T10:00:00Z') == calendar.timegm((2026, 11, 5, 10, 0, 0, 0, 0, 0))
    assert pond.to_epoch('2026-11-05') is None
    assert pond.flip('⠁') == '⠈' and pond.flip('⡇') == '⢸' and pond.flip('x') == 'x'
    assert pond.mirror(pond.mirror(pond.MINI_ROWS)) == list(pond.MINI_ROWS)
    assert pond.wander(0, 0, 10, True)[1] == 1 and pond.wander(20, 0, 10, True)[1] == -1
    busy = dict(pond.demo_ducks()[0]); idle = dict(pond.demo_ducks()[2])
    assert all(pond.EYE not in r for r in pond.pose(busy, 0, 0)[0])
    assert sum(pond.EYE in r for r in pond.pose(busy, 1, 0)[0]) == 1
    assert pond.pose(idle, 5, 0)[1] == 1 and pond.pose(idle, 0, 0)[1] == 0
    fresh = pond.refresh([busy], [dict(busy, status='idle')], 10)
    assert fresh[0]['bubble'] == ('done!', 10)
    assert pond.refresh([], [idle], 20)[0]['bubble'] == ('hello!', 20)
    assert pond.bubble_text(fresh[0], 12, 0) == 'done!' and pond.bubble_text(fresh[0], 40, 0) in ('', 'quack')
    monkeypatch.setattr(pond, 'HOME', '/home/ada')
    assert pond.tilde('/home/ada/code') == '~/code' and pond.tilde('/srv/x') == '/srv/x'
    monkeypatch.setattr(pond, 'PKG', str(tmp_path))
    (tmp_path / 'a.py').write_text('x = 1\n')
    before = pond.source_stamp()
    (tmp_path / 'a.py').write_text('x = (\n')
    assert 'a.py' in pond.source_ok(before, pond.source_stamp())
    (tmp_path / 'a.py').write_text('x = 2\n')
    assert pond.source_ok(before, pond.source_stamp()) is None


def test_header_and_mini_duck():
    import re
    from duckpond import duck
    assert len(duck.MINI_ROWS) == 4 and len({len(r) for r in duck.MINI_ROWS}) == 1
    rows = ['claude\t__NEW__\t/h\t+ new claude session', 'claude\tabc\t/h\tx', 'codex\tdef\t/h\ty']
    text = re.sub(r'\x1b\[[0-9;]*m', '', picker.header(rows))
    assert 'duckpond' in text and 'all your AI sessions, one pond' in text
    assert '2 sessions from claude, codex' in text and 'Hit ?' in text and 'Esc to exit' in text
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


def test_pond_btop_panels():
    from duckpond import pond
    graph = pond.plain(pond.braille_graph([0, 0.5, 1.0, 1.0], 2, 2))
    assert len(graph) == 2 and len(graph[0]) == 2 and graph[1][1] == '⣿' and graph[0][0] == '⠀'
    assert pond.stretch([1, 2], 4) == [1, 1, 2, 2]
    m = pond.plain([pond.meter('claude', 0.5, 30, '')])[0]
    assert m.startswith('claude [') and m.endswith('  50%') and m.count('■') == m.count('□')
    b = pond.plain(pond.box('totals', ['a', 'b'], 20, height=5, right='x', num=4))
    assert len(b) == 5 and all(len(line) == 20 for line in b) and '┐⁴totals┌' in b[0] and b[0].endswith(' x ╮')
    assert pond.cells('ab') == 2 and pond.cells('日本') == 4 and pond.cells('e\u0301') == 1 and pond.cells('\x1b[1mx\x1b[0m') == 1
    assert pond.plain([pond.clip('日本語テキスト', 7)])[0] == '日本語…'
    wide = dict(pond.demo_ducks()[0], title='日本語のタイトルがとても長いときにどうなるか', prompt='絵文字 🦆 を含むプロンプト ' * 5)
    for line in pond.plain(pond.frame([wide] + pond.demo_ducks()[1:], 100, 0)):
        assert pond.cells(line) <= 100, line
    now = 1_800_000_000
    entries = [dict(agent='claude', mtime=now - 10, data=dict(root='/p', turns=3, custom=None, ai='t', cost=1.5,
                                                              times=[now - 60, now - 7200, now - 90000])),
               dict(agent='codex', mtime=now - 90000, data=dict(root='/q', turns=1, custom=None, ai='u', cost=None, times=[]))]
    st = pond.stats(entries, now)
    assert st['sessions'] == 2 and st['prompts'] == 4 and st['cost'] == 1.5
    assert st['hours'][23] == 1 and st['hours'][21] == 1 and sum(st['hours']) == 2
    assert st['agents']['claude']['sessions'] == 1 and st['prompts_today'] >= 1
    ducks = pond.demo_ducks()
    net = pond.demo_net(ducks)
    for width, height in ((120, 40), (100, 24), (80, 20)):
        lines = pond.plain(pond.screen(ducks, 0, pond.demo_stats(), net, width, height))
        assert len(lines) <= height and all(len(line) <= width for line in lines)
        assert lines[1].startswith('╭─┐¹pond┌') and '3 sessions · 2 busy' in lines[1]
        assert lines[-1] == 'q quit · r refresh · + - interval 1s · ¹pond ²tokens ³context ⁴totals'
    tall = pond.plain(pond.screen(ducks, 0, pond.demo_stats(), net, 160, 44))
    assert any(line.startswith('╭─┐²tokens┌') and 'today 12M in · 310k out' in line for line in tall)
    assert any('▼ in' in line and '▲ out' in line for line in tall)
    assert any('claude    [' in line and line.strip('│ ').endswith('%') for line in tall) and any('tokens out by agent' in line for line in tall)
    assert any('┐³context┌' in line for line in tall) and any('Rate limi' in line and '168k' in line for line in tall)
    assert any('ctx 168k' in line for line in tall) and any('168k/200k' in line for line in tall)
    assert pond.ctx_limit(0) == 200_000 and pond.ctx_limit(200_000) == 200_000 and pond.ctx_limit(332_000) == 1_000_000
    assert pond.ctx_limit(300_000, 'codex') == 400_000 and pond.ctx_limit(50_000, 'hermes') == 128_000
    assert any(line.count('▼ in') == 1 and '▲ out' in line and '──' in line for line in tall)
    assert any('cache hit [' in line and ' 88%' in line for line in tall) and not any('busy    [' in line for line in tall)
    assert any('$1.55/h' in line and '12 prompts/h' in line and '6h active' in line for line in tall)
    assert any('94% cached' in line for line in tall) and any('worked 8m/10m' in line for line in tall)
    assert pond.worked([(0, True), (10, True), (20, False), (30, False)], 30) == (20.0, 30.0) and pond.worked([(0, True)], 5) == (0.0, 0.0)
    assert any('tok in' in line and 'tok out' in line for line in tall)
    assert any('tok 4.1M in · 61k out' in line for line in tall)
    assert any('24h ' in line and 'peak 10/h' in line for line in tall)
    short = pond.plain(pond.screen(ducks, 0, pond.demo_stats(), net, 120, 22))
    assert len(short) <= 22 and not any('the burst window' in line for line in short)
    assert any('⚙ Bash' in line for line in short) and any('²tokens┌' in line for line in short)
    assert pond.scaled([0, 1, 3]) == [0.0, 1 / 3, 1.0] and pond.scaled([]) == [] and pond.scaled([0, 0]) == [0.0, 0.0]
    lg = pond.scaled([0, 1, 1000], log=True)
    assert lg[0] == 0.0 and lg[2] == 1.0 and 0.09 < lg[1] < 0.11
    assert any('▼ in' in line and 'log scale' in line for line in tall)
    assert any('▲900/m' in line for line in tall)
    for w in range(96, 110):
        for line in pond.plain(pond.screen(ducks, 0, pond.demo_stats(), net, w, 30)):
            assert len(line) <= w, (w, line)
    assert pond.plain([pond.clip('abcdef', 4)])[0] == 'abc…' and pond.clip('abc', 4) == 'abc'
    assert pond.plain([pond.clip('\x1b[2mabcd\x1b[0mef', 4)])[0] == 'abc…'
    for hidden in ({'pond'}, {'tokens'}, {'burn'}, {'totals'}, {'tokens', 'burn'}, {'tokens', 'totals'}, {'pond', 'burn', 'totals'}, set(pond.BOXES)):
        for w in (80, 100, 120, 159):
            out = pond.plain(pond.screen(ducks, 0, pond.demo_stats(), net, w, 40, hidden=hidden))
            assert len(out) <= 40 and all(len(line) <= w for line in out), (hidden, w)
            text = '\n'.join(out)
            assert not any(f'{b}┌' in text for b in hidden), (hidden, w)
            if w >= 100:
                assert all(f'{b}┌' in text for b in pond.BOXES if b not in hidden), (hidden, w)
    alone = pond.plain(pond.screen(ducks, 0, pond.demo_stats(), net, 120, 50, hidden={'tokens', 'context', 'totals'}))
    assert len(alone) == 50 and alone[-3].startswith('╰') and sum(1 for l in alone if '⣀' in l and '⠉' in l) >= 6
    assert any('the burst window' in line for line in alone)
    empty_alone = pond.plain(pond.screen([], 0, pond.demo_stats(), net, 120, 40, hidden={'tokens', 'context', 'totals'}))
    assert len(empty_alone) == 40 and any('no sessions running' in line for line in empty_alone)
    hid = pond.plain(pond.screen(ducks, 0, pond.demo_stats(), net, 120, 40, hidden={'context'}))
    assert hid[-1].endswith('¹pond ²tokens ³context ⁴totals') and any('²tokens┌' in line and '⁴totals┌' in line for line in hid)
    assert pond.vflip('⠁') == '⡀' and pond.vflip(pond.vflip('⣷')) == '⣷' and pond.vflip('x') == 'x'
    assert pond.human(999) == '999' and pond.human(1234) == '1.2k' and pond.human(61_000) == '61k' and pond.human(4_100_000) == '4.1M'
    s = pond.Sampler()
    a = dict(sid='a', tin=100, tout=10, cached=0, status='busy', cost=1.0)
    s.sample([a], now=1000.0)
    a['tin'], a['tout'], a['cost'] = 700, 70, 1.02
    s.sample([a], now=1002.0)
    assert a['rate'] == (300.0, 30.0) and s.tin[-1] == 300.0 and s.busy == [1.0, 1.0]
    assert a['worked'] == (2.0, 2.0) and abs(s.burn[-1] - 36.0) < 1e-6
    s.sample([a], now=1030.0)
    assert a['rate'] == (20.0, 2.0) and abs(s.burn[-1] - 2.4) < 1e-6
    s.sample([a], now=1070.0)
    assert a['rate'] == (0.0, 0.0) and s.burn[-1] == 0.0
    s.sample([], now=1003.0)
    assert s.hist == {} and s.rate_in == 0.0
