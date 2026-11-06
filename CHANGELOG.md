# Changelog

## 0.3.0

- Renamed to duckpond. The command is `duckpond`; `aisp` stays as a short alias. Cache moved to `~/.cache/duckpond`, settings to `~/.config/duckpond`.
- One-line installers for Linux, macOS (`install.sh`) and Windows (`install.ps1`), with `--uninstall`, verified in CI.
- Green dithered-dot duck app icon (SVG, PNG, ICO, ICNS), the Braille duck banner in `duckpond --help` and `duckpond doctor`, and duck branding in the picker frame.
- `duckpond pond`: the agents running right now, as ducks on a pond. `aisp` is an alias for `duckpond`.
- The pond is a btop-style heads-up display that fills the terminal: a pond box with a card under each duck (status, age and minutes worked out of the last ten, title, directory and branch, uptime, prompts, cost, cache hit rate, tokens in and out with live rates and a sparkline, ducklings, the tool running now, the last prompt; compact on short terminals), then tiled panels titled the btop way (┐¹pond┌): a network-style tokens graph (in up, out down, both log scaled, one-minute averages), a context box with a graph and a meter per session against its 200k or 1M window, and totals with cache hit rate, per-agent meters and today's rates per active hour.
- Ducks are alive: busy ducks bob and ripple, all of them blink, paddle back and forth and turn to face the way they go, idle ducks hop and quack now and then, and a bubble says hello, on it or done when a session appears or changes state. Subagents (Agent tool calls still running) paddle behind their parent as ducklings.
- Pond keys: 1-4 toggle the pond, tokens, context and totals boxes (remembered as the `pond_hidden` setting), + and - change the refresh interval, r refreshes, q or Esc quits. The pond restarts itself when its own source changes.
- One token standard across agents (in, cached, out, ctx, prompts), documented in the README; Hermes now counts cache reads and writes in "in" and reasoning in "out".
- Two more agents: GitHub Copilot CLI (`~/.copilot/session-state/*/events.jsonl`, resume with `copilot --resume`) and Copilot Chat in VS Code (`workspaceStorage/*/chatSessions/*.jsonl`, resume opens the workspace with `code -r`). Both get list, preview, export, handoff, picker and pond support; `COPILOT_HOME` and `DUCKPOND_VSCODE_DIR` override the locations. VS Code chats carry prompt and completion tokens and context size from VS Code's own records; a chat counts as open while a VS Code window is showing it (open windows come from `code --status`, asked in the background at most every 30 seconds and cached; the shown chat from the workspace state database) and busy while a request has no result.
- Hermes subagents (child sessions still running) show as ducklings, Hermes token totals and the last tool come from its database, and harness-injected lines such as delegation batch notices no longer count as prompts.
- Codex: a turn in progress (task_started without task_complete) counts as busy, the context window comes from Codex's own token_count events, and shell, custom and local shell tool calls all show on the card.
- Codex and Hermes sessions written to in the last 15 minutes count as open, and in the last 20 seconds as busy, so they appear in the pond and get the dot in the picker.
- `duckpond pond --interval S` sets the refresh interval from the shell.
- Picker: Alt-X hides every session and Alt-R rebuilds the index, each after a y/n prompt on the terminal; `duckpond hide-all` and `duckpond rebuild` do the same from the shell.
- `duckpond last [words]` resumes the most recent session, optionally the most recent one matching the words.
- The index now records the tool each session last called, its running subagents, prompt timestamps, tokens in, out and cached per minute, and the current context size (index v14, rebuilt automatically).
- SECURITY.md and an expanded privacy section.
- CI runs on pull requests, tags and by hand instead of on every push.
- Requirements section and `requirements-dev.txt`.
- Installer and doctor tell you how to get a missing dependency on your platform. Fixed the installer looping forever on machines without fzf.
- `duckpond install-skills` gives Claude Code, Codex and Hermes a SKILL.md about duckpond and handoffs.
- `duckpond pond` redrawn with the Braille mini duck and drifting water.
- In-app guide: F1 in the picker and `duckpond help`. Mini duck header with a pond status line, a "back to" line on resume.
- `duckpond config terminal "..."` picks the terminal used by `--window` and the app launcher.
- `duckpond uninstall-launcher`.
- `duckpond install-launcher` registers an "AI Sessions" app with an icon on Linux, macOS and Windows.
- Single `duckpond` command with subcommands: `list`, `preview`, `export`, `hide`, `unhide-all`, `copy`, `doctor`.
- `duckpond list --json` for scripts and integrations.
- `duckpond doctor` reports agents, stores, fzf and cache state.
- Ctrl-P shows the full transcript in the preview pane.
- Test suite with generated sample stores, CI on Linux, macOS and Windows.
- Hermes database opened through a file URI so Windows paths work.

## 0.2.0

- Cross-platform rewrite as a Python package with fzf as the UI.
- Codex and Hermes backends alongside Claude Code.
- Handoff of a conversation from one agent to another.
- Owner-only cache permissions and id validation.

## 0.1.0

- Claude Code only fzf picker.
