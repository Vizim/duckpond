from agent_picker import picker


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
