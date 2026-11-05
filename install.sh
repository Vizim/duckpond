#!/bin/sh
# duckpond installer for Linux and macOS.
#
#   curl -fsSL https://raw.githubusercontent.com/Vizim/duckpond/main/install.sh | sh
#   sh install.sh --uninstall
#
# Installs into a private virtualenv under $DUCKPOND_HOME (default ~/.local/share/duckpond), links duckpond into
# $DUCKPOND_BIN (default ~/.local/bin), fetches fzf there if missing, and registers the app launcher.
set -eu

REPO="https://github.com/Vizim/duckpond"
DUCKPOND_HOME="${DUCKPOND_HOME:-$HOME/.local/share/duckpond}"
DUCKPOND_BIN="${DUCKPOND_BIN:-$HOME/.local/bin}"
VENV="$DUCKPOND_HOME/venv"

say() { printf '%s\n' "$*"; }
die() { printf 'duckpond install: %s\n' "$*" >&2; exit 1; }
ask() {  # ask "question" -> 0 for yes; defaults to no when there is no terminal
  reply=""
  if [ -t 0 ]; then
    printf '%s [y/N] ' "$1"; read -r reply || reply=""
  elif { exec 3</dev/tty; } 2>/dev/null; then
    printf '%s [y/N] ' "$1"; read -r reply <&3 || reply=""; exec 3<&-
  fi
  case "$reply" in y|Y|yes) return 0 ;; *) return 1 ;; esac
}

uninstall() {
  [ -x "$VENV/bin/duckpond" ] && "$VENV/bin/duckpond" uninstall-launcher || true
  rm -rf "$DUCKPOND_HOME"
  [ -L "$DUCKPOND_BIN/duckpond" ] && rm -f "$DUCKPOND_BIN/duckpond"
  [ -L "$DUCKPOND_BIN/aisp" ] && rm -f "$DUCKPOND_BIN/aisp"
  [ -f "$DUCKPOND_BIN/.duckpond-installed-fzf" ] && rm -f "$DUCKPOND_BIN/fzf" "$DUCKPOND_BIN/.duckpond-installed-fzf"
  cache="${DUCKPOND_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/agent-picker}"
  if [ -d "$cache" ] && ask "also remove the cache with session previews at $cache?"; then rm -rf "$cache"; fi
  say "duckpond removed"
}

find_python() {
  for py in python3 python3.13 python3.12 python3.11 python3.10 python3.9 python; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
      command -v "$py"; return 0
    fi
  done
  return 1
}

install_fzf() {
  command -v fzf >/dev/null 2>&1 && return 0
  if [ "$(uname -s)" = Darwin ] && command -v brew >/dev/null 2>&1; then
    say "installing fzf with Homebrew"; brew install -q fzf && return 0
  fi
  os=$(uname -s | tr '[:upper:]' '[:lower:]'); arch=$(uname -m)
  case "$arch" in x86_64|amd64) arch=amd64 ;; aarch64|arm64) arch=arm64 ;; armv7l) arch=armv7 ;; *) die "no fzf build for $arch, install fzf yourself: https://github.com/junegunn/fzf#installation" ;; esac
  ver=$(latest_fzf) || die "could not look up the latest fzf release, install fzf yourself: https://github.com/junegunn/fzf#installation"
  say "installing fzf $ver into $DUCKPOND_BIN"
  tmp=$(mktemp -d); fetch "https://github.com/junegunn/fzf/releases/download/v$ver/fzf-$ver-${os}_$arch.tar.gz" >"$tmp/fzf.tgz"
  tar -xzf "$tmp/fzf.tgz" -C "$tmp" && install -m 755 "$tmp/fzf" "$DUCKPOND_BIN/fzf" && touch "$DUCKPOND_BIN/.duckpond-installed-fzf"
  rm -rf "$tmp"
}

latest_fzf() {
  # The release redirect needs no API quota; the API is the fallback, with a token when one is set.
  ver=$(curl -fsSI -o /dev/null -w '%{redirect_url}' https://github.com/junegunn/fzf/releases/latest 2>/dev/null | sed -n 's#.*/tag/v\{0,1\}##p')
  if [ -z "$ver" ]; then
    auth=""; [ -n "${GITHUB_TOKEN:-}" ] && auth="Authorization: Bearer $GITHUB_TOKEN"
    ver=$(curl -fsSL ${auth:+-H "$auth"} https://api.github.com/repos/junegunn/fzf/releases/latest 2>/dev/null | sed -n 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p' | head -n1)
  fi
  [ -n "$ver" ] && printf '%s\n' "$ver"
}

fetch() {
  if command -v curl >/dev/null 2>&1; then curl -fsSL "$1"
  elif command -v wget >/dev/null 2>&1; then wget -qO- "$1"
  else die "need curl or wget"; fi
}

install() {
  py=$(find_python) || die "python 3.9 or newer is required (https://www.python.org/downloads/)"
  mkdir -p "$DUCKPOND_HOME" "$DUCKPOND_BIN"
  say "creating virtualenv in $VENV"
  "$py" -m venv "$VENV" 2>/dev/null || die "could not create a virtualenv; on Debian or Ubuntu run: sudo apt install python3-venv"
  src="git+$REPO"
  here=$(cd "$(dirname "$0")" 2>/dev/null && pwd || true)
  [ -n "$here" ] && [ -f "$here/pyproject.toml" ] && src="$here"
  say "installing duckpond from $src"
  "$VENV/bin/python" -m pip install -q --upgrade pip
  "$VENV/bin/python" -m pip install -q --upgrade "$src"
  ln -sf "$VENV/bin/duckpond" "$DUCKPOND_BIN/duckpond"
  ln -sf "$VENV/bin/aisp" "$DUCKPOND_BIN/aisp"
  install_fzf
  case ":$PATH:" in *":$DUCKPOND_BIN:"*) ;; *) say ""; say "add this to your shell profile so the duckpond command is found:"; say "  export PATH=\"$DUCKPOND_BIN:\$PATH\""; say "" ;; esac
  export PATH="$DUCKPOND_BIN:$PATH"
  "$VENV/bin/duckpond" install-launcher || say "launcher not registered, run 'duckpond install-launcher' later"
  say ""
  "$VENV/bin/duckpond" doctor || true
  say ""
  say "done. run: duckpond"
}

case "${1:-}" in
  --uninstall|uninstall) uninstall ;;
  "") install ;;
  *) die "usage: install.sh [--uninstall]" ;;
esac
