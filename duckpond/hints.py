"""What to tell someone when a dependency is missing, matched to their platform."""
import shutil
import sys


def package_manager():
    for name in ('brew', 'apt', 'dnf', 'pacman', 'zypper', 'winget', 'scoop', 'choco'):
        if shutil.which(name):
            return name
    return None


FZF = {
    'brew': 'brew install fzf',
    'apt': 'sudo apt install fzf',
    'dnf': 'sudo dnf install fzf',
    'pacman': 'sudo pacman -S fzf',
    'zypper': 'sudo zypper install fzf',
    'winget': 'winget install fzf',
    'scoop': 'scoop install fzf',
    'choco': 'choco install fzf',
}

AGENTS = {
    'claude': ('Claude Code', 'npm install -g @anthropic-ai/claude-code    or see https://code.claude.com/docs/en/overview'),
    'codex': ('Codex', 'npm install -g @openai/codex    or see https://github.com/openai/codex'),
    'hermes': ('Hermes', 'see https://github.com/NousResearch/hermes-agent'),
    'copilot': ('Copilot CLI', 'npm install -g @github/copilot    or see https://github.com/github/copilot-cli'),
    'vscode': ('VS Code', 'install VS Code with the GitHub Copilot Chat extension, see https://code.visualstudio.com'),
}


def fzf_hint():
    pm = package_manager()
    if pm in FZF:
        return f'fzf is missing. install it with: {FZF[pm]}'
    if sys.platform == 'win32':
        return 'fzf is missing. install it with winget, scoop or choco, or download a release from https://github.com/junegunn/fzf/releases'
    return 'fzf is missing. download a release from https://github.com/junegunn/fzf/releases and put it on your PATH'


def agent_hint(agent):
    name, how = AGENTS[agent]
    return f'{name} is not on PATH. to install: {how}'


def no_agents_hint():
    return ('no agent found on PATH. duckpond lists sessions from whichever of these you install:\n'
            + '\n'.join(f'  {name:<12} {how}' for name, how in AGENTS.values()))
