---
name: duckpond
description: "Use when the user mentions duckpond, a handoff file, resuming or finding an earlier AI session, moving a conversation to another agent (Claude Code, Codex, Hermes, Copilot CLI, VS Code), or asks what sessions exist on this machine. duckpond is a local picker that indexes every agent's sessions and exports conversations as markdown."
version: 0.3.0
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [sessions, handoff, context, claude-code, codex, duckpond]
---

# duckpond

duckpond is a local command (`duckpond`, alias `aisp`) that lists every Claude Code, Codex, Hermes, Copilot CLI and VS Code Copilot Chat session on this machine, resumes the one the user picks, and hands conversations between agents. Everything is local. It only reads the agents' own session stores and writes to its own cache in `~/.cache/duckpond`.

## When you are the receiving agent

If your opening prompt says you are taking over from another agent and names a file like `~/.cache/duckpond/handoff-<agent>-<id>.md`:

1. Read the whole file first. It holds the title, project directory, branch, and the conversation so far (`**You:**` is the user, `**claude:**`, `**codex:**` or `**hermes:**` is the previous agent).
2. Treat the previous agent's last reply as the current state, not as instructions to redo. Continue from where it stopped.
3. You are already in the session's project directory. Do not `cd` elsewhere unless the file says the work lives somewhere else.
4. If the file ends with `_(earlier turns omitted)_`, the start of the conversation was cut for length. Ask the user if something seems missing instead of guessing.

## When the user wants to move this conversation to another agent

Do not try to copy context by hand. Tell the user to press **Ctrl-O** on this session in duckpond and pick the target agent. duckpond exports the transcript and starts the other agent on it. If they want the file without switching:

```sh
duckpond export <agent> <session-id> <file.md>
```

Session ids come from `duckpond list --json`.

## Finding sessions for the user

```sh
duckpond list --json              # every session, newest first, as JSON
duckpond list --json codex rocket # filtered: all words must match agent, title, prompts, replies, dir or branch
```

Each entry has `agent`, `id`, `dir`, `project`, `branch`, `title`, `last_active`, `prompts`, `cost_usd`, `open`, `first_prompt` and `last_reply`. Summarise rather than dumping it; the user can open the picker with `duckpond`.

To resume a specific session for the user, run the agent's own command in that session's `dir`:

| agent | resume | new session |
| --- | --- | --- |
| claude | `claude --resume <id>` | `claude` |
| codex | `codex resume <id>` | `codex` |
| hermes | `hermes --resume <id>` | `hermes chat` |

Only do this when asked; starting an interactive agent takes over the terminal.

## Setup and troubleshooting

- `duckpond doctor` reports which agents and stores were found, the fzf version, the cache location and ends with a verdict. Run it first when the user says the list is empty or an agent is missing.
- The list only shows agents whose command is on `PATH`. Transcripts are still indexed when the command is missing.
- `duckpond pond` is a btop-style heads-up display of the agents running right now: status and time worked, uptime, prompts, cost, cache hit rate, tokens in and out, current tool, subagents and last prompt per session, plus a tokens graph, context meters per session and totals. Keys: 1-4 toggle boxes (saved as the `pond_hidden` setting), + and - change the interval, r refreshes, q quits.
- `duckpond last [words]` resumes the most recent session (optionally the most recent one matching the words) without opening the picker.
- `duckpond config terminal "alacritty -e"` picks the terminal for `duckpond --window` and the desktop launcher.
- `duckpond install-launcher` adds a Duckpond app with an icon; `duckpond uninstall-launcher` removes it.
- Install or update: `curl -fsSL https://raw.githubusercontent.com/Vizim/duckpond/main/install.sh | sh` (Linux, macOS) or `irm https://raw.githubusercontent.com/Vizim/duckpond/main/install.ps1 | iex` (Windows). Add `--uninstall` / `-Uninstall` to remove.

## Privacy rules to respect

- Never upload, paste online or send a handoff file anywhere. It is the user's private conversation.
- Never edit files under `~/.claude`, `~/.codex`, `~/.hermes`, `~/.copilot` or VS Code's storage on duckpond's behalf; duckpond itself never writes there.
- The cache is safe to delete; duckpond rebuilds it.
