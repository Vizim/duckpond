#!/bin/bash
# Symlink the picker into ~/.local/bin and register the desktop entry.
set -eu
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
ln -sf "$here/claude-picker" "$HOME/.local/bin/claude-picker"
ln -sf "$here/claude-sessions.py" "$HOME/.local/bin/claude-sessions.py"
install -m 644 "$here/claude-picker.desktop" "$HOME/.local/share/applications/claude-picker.desktop"
echo "installed: run claude-picker, or 'Claude Code Sessions' from your launcher"
