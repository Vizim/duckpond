# claude-code-session-picker

A fast fzf picker for your recent [Claude Code](https://claude.com/claude-code) sessions, across every project on the machine.

Claude Code's own `/resume` only lists sessions for the folder you launched it from. This picker reads all of them, gives each one a title and a preview of what you asked and what Claude last said, and resumes the one you pick in the right directory.

## Features

- One list for all projects, newest first, with a green dot on sessions that are open in another window
- Search as you type across titles, your prompts, replies, branch and directory
- Preview pane: project, branch, active dates, prompt count, cost, the prompts you typed and the last reply
- Resume in the session's project directory, or wherever you last typed `!cd` inside it
- Live refresh while sessions are writing, without re-reading whole transcripts
- Fork a session, start a new one in a row's project, pull down a claude.ai/code session, hide rows, copy ids

| Key | Action |
| --- | --- |
| Enter | Resume the session |
| Ctrl-F | Resume as a fork (new session id) |
| Ctrl-N | New session in that row's directory |
| Ctrl-T | List cloud sessions for that row's directory (`claude --teleport`) |
| Ctrl-X | Hide the row |
| Ctrl-U | Unhide everything |
| Ctrl-Y | Copy the session id |
| Ctrl-R | Refresh |

## Install

Requires `claude`, `fzf` (0.44 or newer), `python3`, `curl` and `ss` (iproute2). Copying ids uses `wl-copy` or `xclip` if present.

```sh
git clone https://github.com/Vizim/claude-code-session-picker
cd claude-code-session-picker
./install.sh
```

That links `claude-picker` into `~/.local/bin` and adds a "Claude Code Sessions" desktop entry. Then:

```sh
claude-picker            # in the current terminal
claude-picker --window   # in a new terminal window (kitty by default)
```

## Configuration

Everything is an environment variable.

| Variable | Default | Meaning |
| --- | --- | --- |
| `CLAUDE_PICKER_TERMINAL` | `kitty` | Terminal used by `--window`; it must accept `-e command` |
| `CLAUDE_PICKER_CACHE` | `~/.cache/claude-picker` | Index, previews and the hidden list |
| `CLAUDE_PICKER_PORT` | `44144` | fzf control port on 127.0.0.1, falls back to a free one |

## How it works

`claude-sessions.py` scans `~/.claude/projects/*/*.jsonl`, keeps a small per-session summary in the cache, and only reads the bytes appended since its last run. Each keystroke in fzf re-runs it with the query, so matching happens in Python and the list stays in time order. A watcher process pokes fzf over its listen port whenever a transcript changes. Live sessions come from `~/.claude/sessions/*.json`, checked against the recorded process start time so a reused pid is not mistaken for a running session.

Nothing is sent anywhere, and transcripts are never modified. Hiding a row only writes its id to `hidden.json` in the cache.

## License

MIT
