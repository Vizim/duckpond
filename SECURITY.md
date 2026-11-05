# Security

## What this program touches

duckpond reads the session stores that Claude Code, Codex and Hermes already keep on your machine, and writes a cache of its own. That is the whole surface.

| | Path | Access |
| --- | --- | --- |
| Claude Code transcripts | `~/.claude/projects/*/*.jsonl` | read only |
| Claude Code lock files | `~/.claude/sessions/*.json` | read only, to show which sessions are open |
| Codex rollouts | `~/.codex/sessions/**/*.jsonl` | read only |
| Hermes store | `~/.hermes/state.db` | read only, opened with SQLite `mode=ro` |
| duckpond cache | `~/.cache/duckpond/` | read and write, created `0700`, files `0600` |
| duckpond settings | `~/.config/duckpond/config.ini` | read and write, holds only the terminal command |
| Launcher files | desktop entry, `.app` bundle or `.lnk` | written by `install-launcher`, removed by `uninstall-launcher` |
| Agent skill files | `~/.claude/skills/duckpond`, `~/.codex/skills/duckpond`, `~/.hermes/skills/duckpond` | written only by the opt-in `install-skills`, removed by `uninstall-skills` |

The cache holds a summary of each session (title, directory, your prompts, the last reply) and, after a handoff or a full-transcript preview, a markdown copy of that conversation. It is the only place duckpond copies your data to, and it stays on this machine with owner-only permissions. Delete it at any time; duckpond rebuilds it.

## What this program never does

- It never sends anything over the network. The only socket it opens is fzf's control port on `127.0.0.1`, protected by a random key generated for each launch, used to refresh the list.
- It never reads, stores or forwards credentials. Signing in to an agent happens in that agent's own flow. duckpond only runs `claude`, `codex` or `hermes` as you would in a shell.
- It never modifies an agent's session store. Hiding a session writes its id to the cache; nothing is deleted or edited there. The only write under an agent's home is the opt-in skill folder above.
- It has no telemetry, no update check and no third-party dependencies beyond fzf and the Python standard library.
- It never runs anything found inside a transcript. Session ids are validated against a strict character set before they are used in a file name or a command, and all commands are run as argument lists, never through a shell.

The two actions that do reach the network are Claude Code's own: Ctrl-T and the cloud-link row run `claude --teleport`, which talks to Anthropic on your behalf, only when you press them.

## Reporting a vulnerability

Open a private security advisory on the GitHub repository, or email the maintainer address on the GitHub profile. Please include the version from `duckpond --version`, your platform and steps to reproduce. You should hear back within a week.
