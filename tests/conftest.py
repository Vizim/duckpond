import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import sample_stores  # noqa: E402


@pytest.fixture
def stores(tmp_path, monkeypatch):
    """Sample stores plus a reloaded sessions module pointed at them."""
    root = str(tmp_path / 'stores')
    ids = sample_stores.build(root)
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', os.path.join(root, 'claude'))
    monkeypatch.setenv('CODEX_HOME', os.path.join(root, 'codex'))
    monkeypatch.setenv('HERMES_HOME', os.path.join(root, 'hermes'))
    monkeypatch.setenv('DUCKPOND_CACHE', str(tmp_path / 'cache'))
    from duckpond import sessions
    importlib.reload(sessions)
    return dict(root=root, ids=ids, sessions=sessions, cache=str(tmp_path / 'cache'))
