# ai-session-picker

One picker for every coding-agent session on your machine: [Claude Code](https://claude.com/claude-code), [Codex](https://github.com/openai/codex) and [Hermes](https://github.com/NousResearch/hermes-agent), across all projects, in fzf.

Each agent's own resume command only shows the sessions for the folder you launched it from, and each has its own list. This picker reads all of them, gives every session a title and a preview of what you asked and what the agent last said, and resumes the one you pick in the right directory with the right agent. It can also hand a conversation from one agent to another.

![aisp showing Claude, Codex and Hermes sessions with a preview pane](docs/picker.svg)

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
| Ctrl-P | Show the full transcript in the preview pane |
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
aisp            # in the current terminal
aisp --window   # in a new terminal window
aisp doctor     # check agents, stores, fzf and the cache
```

`--window` uses the first terminal it finds on Linux (kitty, alacritty, foot, wezterm, gnome-terminal, konsole, xfce4-terminal, xterm), Terminal.app on macOS and Windows Terminal or cmd on Windows. `packaging/aisp.desktop` is a launcher entry for Linux desktops.

Without installing, run it from a clone with `python -m agent_picker.cli`.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `AGENT_PICKER_TERMINAL` | per OS | Command that runs a program in a new window, e.g. `kitty -e` or `alacritty -e` |
| `AGENT_PICKER_CACHE` | `~/.cache/agent-picker` | Index, previews, handoff files and the hidden list |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | Where Claude Code keeps its transcripts |
| `CODEX_HOME` | `~/.codex` | Where Codex keeps its rollouts |
| `HERMES_HOME` | `~/.hermes` | Where Hermes keeps its SQLite store |

## Scripting

`aisp list --json` prints every session as JSON (agent, id, directory, project, branch, title, last activity, prompt count, cost, first prompt, last reply), newest first. `aisp list codex rocket` applies the same search the picker does. `aisp export AGENT ID FILE` writes one conversation as markdown.

## Handing off between agents

Press Ctrl-O on a session and pick the target agent. The picker writes the conversation (your prompts and the agent's replies, newest 200 KB if it is long) to a markdown file in the cache, then starts the target in the session's directory with an opening prompt that points at the file. Claude and Codex take that prompt on the command line. Hermes cannot take an opening prompt and stay interactive, so the picker starts `hermes chat` and puts the prompt on your clipboard to paste.

## Privacy

Everything stays on your machine.

- Session stores are only ever read. Transcript files are opened read-only and the Hermes database is opened in SQLite read-only mode.
- The cache holds copies of prompts and replies, so it is created with owner-only permissions (`0700` directory, `0600` files).
- The only network traffic is fzf's control socket on `127.0.0.1`, protected by a random per-launch key, which the picker uses to refresh the list. Nothing is sent anywhere else. Ctrl-T and the cloud-link row call Claude Code's own `--teleport`, which talks to Anthropic on your behalf and only when you ask.
- Hiding a row writes its id to `hidden.json`. Nothing is deleted.

## How it works

`aisp list` builds the list. For Claude and Codex it scans the JSONL transcripts and remembers how far it read, so a changed file costs only its new bytes. For Hermes it queries `state.db`. Each keystroke in fzf re-runs it with the query, so matching happens in Python and the list stays in time order. A thread in the picker watches the stores and pokes fzf over its listen port when something changes. Live Claude sessions come from its lock files, checked against the recorded process start time on Linux so a reused pid is not mistaken for a running session.

## Development

```sh
git clone https://github.com/Vizim/ai-session-picker
cd ai-session-picker
python -m pip install -e . pytest
python -m pytest -q
```

Tests run against generated sample stores, never your real sessions, and CI runs them on Linux, macOS and Windows. `python tests/sample_stores.py DIR` builds the same sample set to try the picker on; see CONTRIBUTING.md.

## Similar tools

[Agent Sessions](https://github.com/jazzyalex/agent-sessions) is a native macOS app that browses and resumes sessions from many agents with full transcript search. [agent-sessions](https://github.com/vineethkrishnan/agent-sessions) is a Node TUI for Claude Code, Cursor, Gemini CLI, Codex and Windsurf. [agent-session](https://github.com/anaknegeri/agent-session) keeps a separate project notebook that agents hand to each other. This project differs in being one stdlib Python command for Linux, macOS and Windows, covering Hermes, refreshing live, and handing off from the agents' own transcripts.

## License and trademarks

MIT. This is an independent project. Claude Code is a product of Anthropic, Codex of OpenAI and Hermes of Nous Research. Their names are used only to say which tools this picker works with. None of them built, endorse or are affiliated with it, and it ships none of their software: each agent is installed and signed into through its own official flow, and the picker only launches it.
