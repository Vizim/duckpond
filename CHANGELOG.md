# Changelog

## 0.3.0

- Renamed to duckpond. The command is `duckpond`; `aisp` stays as a short alias. Cache moved to `~/.cache/duckpond`, settings to `~/.config/duckpond`.
- One-line installers for Linux, macOS (`install.sh`) and Windows (`install.ps1`), with `--uninstall`, verified in CI.
- Rubber duck app icon (SVG, PNG, ICO, ICNS) and the Braille duck banner in `duckpond --help` and `duckpond doctor`.
- `duckpond pond`: the agents running right now, as ducks on a pond. `duckpond` is an alias for `duckpond`.
- SECURITY.md and an expanded privacy section.
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
