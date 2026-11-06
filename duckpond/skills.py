"""duckpond install-skills: give each installed agent a SKILL.md that explains duckpond and handoffs."""
import os
import shutil

from . import sessions

SOURCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills', 'duckpond', 'SKILL.md')
HOMES = {'claude': sessions.CLAUDE_HOME, 'codex': sessions.CODEX_HOME, 'hermes': sessions.HERMES_HOME,
         'copilot': sessions.COPILOT_HOME}


def targets(agents=None):
    # Only agents that are installed, or whose home already exists, get a copy.
    out = {}
    for agent, home in HOMES.items():
        if agents is not None and agent not in agents:
            continue
        if agent in sessions.installed() or os.path.isdir(home):
            out[agent] = os.path.join(home, 'skills', 'duckpond', 'SKILL.md')
    return out


def install(agents=None):
    done = []
    for agent, path in targets(agents).items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copyfile(SOURCE, path)
        done.append(f'  {agent:<7} {path}')
    if not done:
        return 'no agent homes found; install Claude Code, Codex or Hermes first'
    return 'installed the duckpond skill for:\n' + '\n'.join(done) + '\nagents will pick it up on their next session'


def uninstall():
    gone = []
    for agent, path in targets().items():
        folder = os.path.dirname(path)
        if os.path.isdir(folder):
            shutil.rmtree(folder, ignore_errors=True)
            gone.append(f'  {agent:<7} {folder}')
    return 'removed:\n' + '\n'.join(gone) if gone else 'no duckpond skill was installed'
