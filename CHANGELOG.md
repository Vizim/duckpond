# Changelog

## 0.3.0

- One-line installers for Linux, macOS (`install.sh`) and Windows (`install.ps1`), with `--uninstall`, verified in CI.
- ASCII duck in `aisp --help` and `aisp doctor`.
- `aisp config terminal "..."` picks the terminal used by `--window` and the app launcher.
- `aisp uninstall-launcher`.
- `aisp install-launcher` registers an "AI Sessions" app with an icon on Linux, macOS and Windows.
- Single `aisp` command with subcommands: `list`, `preview`, `export`, `hide`, `unhide-all`, `copy`, `doctor`.
- `aisp list --json` for scripts and integrations.
- `aisp doctor` reports agents, stores, fzf and cache state.
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
