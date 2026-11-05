# ai-session-picker

One picker for every coding-agent session on your machine: [Claude Code](https://claude.com/claude-code), [Codex](https://github.com/openai/codex) and [Hermes](https://github.com/NousResearch/hermes-agent), across all projects, in fzf.

Each agent's own resume command only shows the sessions for the folder you launched it from, and each has its own list. This picker reads all of them, gives every session a title and a preview of what you asked and what the agent last said, and resumes the one you pick in the right directory with the right agent. It can also hand a conversation from one agent to another.

![agent-picker showing Claude, Codex and Hermes sessions with a preview pane](docs/picker.svg)

*Screenshot rendered from generated sample data.*

## Features

- One list for all agents and all projects, newest first, with a green dot on sessions that are open right now
- Search as you type across agent, title, your prompts, replies, branch and directory
- Preview pane: project, branch, active dates, prompt count, cost, the prompts you typed and the last reply
- Resume in the session's project directory, or wherever you last typed `!cd` inside it
- Hand off: export a session's conversation to a private markdown file and open a different agent on it in the same directory
- Live refresh while sessions are writing, without re-reading whole transcripts
- Fork, start a new session in a row's project, pull down a claude.ai/code session, hide rows, copy ids

| Key | Action |
| --- | --- |
| Enter | Resume the session with its agent |
| Ctrl-O | Hand off to another agent (pick the target, it opens with the conversation as context) |
| Ctrl-F | Resume as a fork with a new session id (Claude; others resume) |
| Ctrl-N | New session of that row's agent in that row's directory |
| Ctrl-T | List cloud sessions for that row's directory (`claude --teleport`) |
| Ctrl-X | Hide the row |
| Ctrl-U | Unhide everything |
| Ctrl-Y | Copy the session id |
| Ctrl-R | Refresh |

Type an agent name to filter to it, for example `codex` or `hermes rocket`.

## Install

Linux, macOS and Windows. Requires Python 3.8 or newer and [fzf](https://github.com/junegunn/fzf#installation) 0.44 or newer on your PATH, plus whichever agents you use.

```sh
pipx install git+https://github.com/Vizim/ai-session-picker
```

or, from a clone, `pip install .` or `pipx install .`. Then:

```sh
agent-picker            # in the current terminal
agent-picker --window   # in a new terminal window
```

`--window` uses the first terminal it finds on Linux (kitty, alacritty, foot, wezterm, gnome-terminal, konsole, xfce4-terminal, xterm), Terminal.app on macOS and Windows Terminal or cmd on Windows. `packaging/agent-picker.desktop` is a launcher entry for Linux desktops.

Without installing, run it from a clone with `python -m agent_picker.picker`.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `AGENT_PICKER_TERMINAL` | per OS | Command that runs a program in a new window, e.g. `kitty -e` or `alacritty -e` |
| `AGENT_PICKER_CACHE` | `~/.cache/agent-picker` | Index, previews, handoff files and the hidden list |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | Where Claude Code keeps its transcripts |
| `CODEX_HOME` | `~/.codex` | Where Codex keeps its rollouts |
| `HERMES_HOME` | `~/.hermes` | Where Hermes keeps its SQLite store |

## Handing off between agents

Press Ctrl-O on a session and pick the target agent. The picker writes the conversation (your prompts and the agent's replies, newest 200 KB if it is long) to a markdown file in the cache, then starts the target in the session's directory with an opening prompt that points at the file. Claude and Codex take that prompt on the command line. Hermes cannot take an opening prompt and stay interactive, so the picker starts `hermes chat` and puts the prompt on your clipboard to paste.

## Privacy

Everything stays on your machine.

- Session stores are only ever read. Transcript files are opened read-only and the Hermes database is opened in SQLite read-only mode.
- The cache holds copies of prompts and replies, so it is created with owner-only permissions (`0700` directory, `0600` files).
- The only network traffic is fzf's control socket on `127.0.0.1`, protected by a random per-launch key, which the picker uses to refresh the list. Nothing is sent anywhere else. Ctrl-T and the cloud-link row call Claude Code's own `--teleport`, which talks to Anthropic on your behalf and only when you ask.
- Hiding a row writes its id to `hidden.json`. Nothing is deleted.

## How it works

`agent-sessions` builds the list. For Claude and Codex it scans the JSONL transcripts and remembers how far it read, so a changed file costs only its new bytes. For Hermes it queries `state.db`. Each keystroke in fzf re-runs it with the query, so matching happens in Python and the list stays in time order. A thread in `agent-picker` watches the stores and pokes fzf over its listen port when something changes. Live Claude sessions come from its lock files, checked against the recorded process start time on Linux so a reused pid is not mistaken for a running session.

## Development

```sh
git clone https://github.com/Vizim/ai-session-picker
cd ai-session-picker
python -m agent_picker.picker
```

Point the `*_HOME` variables above at a directory of sample stores to try it without your real sessions.

## License

MIT
