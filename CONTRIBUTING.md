# Contributing

Thanks for helping. The project is small on purpose: standard library Python plus fzf, nothing else to install.

## Setup

```sh
git clone https://github.com/Vizim/ai-session-picker
cd ai-session-picker
python -m pip install -e . pytest
python -m pytest -q
```

Try the picker against generated sample data instead of your real sessions:

```sh
python tests/sample_stores.py /tmp/aisp-sample
CLAUDE_CONFIG_DIR=/tmp/aisp-sample/claude CODEX_HOME=/tmp/aisp-sample/codex \
HERMES_HOME=/tmp/aisp-sample/hermes AGENT_PICKER_CACHE=/tmp/aisp-sample/cache aisp
```

## Adding an agent

An agent needs three things in `agent_picker/sessions.py`:

1. Where its sessions live and how to turn one into the common state dict (`new_state()`): see `claude_feed` and `codex_feed` for line-based transcripts, or `collect_hermes` for a database.
2. An entry in `AGENTS` (binary name and colour) and in `COMMANDS` in `picker.py` (how to start a new session and how to resume one).
3. A generator in `tests/sample_stores.py` that writes a realistic sample, and tests that list, preview and export it.

Keep reads read-only, never touch the agent's own files, and never handle its credentials.

## Rules of thumb

- No third-party runtime dependencies.
- Anything that touches a user's data stays local and lands in the cache with owner-only permissions.
- Comments are one or two lines, only where the code cannot say it itself.
- Add or update a test for behaviour you change. CI runs on Linux, macOS and Windows.
