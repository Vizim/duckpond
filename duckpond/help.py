"""The in-app guide: duckpond help, and F1 inside the picker."""
from .duck import BOLD, DIM, GREEN, RESET, TAGLINE, mini

KEYS = [
    ('Enter', 'resume the selected session with its agent, in its directory'),
    ('type', 'search titles, prompts, replies, branch, directory and agent name; all words must match'),
    ('Ctrl-O', 'hand off: export this conversation and open another agent on it in the same directory'),
    ('Ctrl-F', 'fork: resume as a new session id (Claude; other agents just resume)'),
    ('Ctrl-N', 'new session of that row\'s agent in that row\'s directory'),
    ('Ctrl-T', 'cloud sessions for that row\'s directory (Claude; others start a new session)'),
    ('Ctrl-P', 'show the whole transcript in the preview; move the cursor to go back'),
    ('Ctrl-X', 'hide the row (nothing is deleted)'),
    ('Ctrl-U', 'unhide everything'),
    ('Alt-X', 'hide every session, after a y/n prompt (nothing is deleted)'),
    ('Alt-R', 'rebuild the index from scratch, after a y/n prompt'),
    ('Ctrl-Y', 'copy the session id'),
    ('Ctrl-R', 'refresh the list'),
    ('?', 'this guide (F1 works too); Enter brings you back'),
    ('Esc', 'leave without doing anything'),
]

COMMANDS = [
    ('duckpond', 'open the picker'),
    ('duckpond --window', 'open it in a new terminal window'),
    ('duckpond pond [--interval S]', 'btop-style heads-up display: ducks, tokens graph, context meters, totals'),
    ('  in the pond', '1-4 toggle boxes, + - refresh interval, r refresh, q or Esc quit'),
    ('duckpond last [words]', 'resume the most recent session, or the most recent one matching the words'),
    ('duckpond list [--json] [words]', 'print the list, optionally filtered, optionally as JSON'),
    ('duckpond export AGENT ID FILE', 'write one conversation as markdown'),
    ('duckpond config terminal "..."', 'choose the terminal used by --window and the app launcher'),
    ('duckpond install-launcher', 'add a Duckpond app with an icon to this desktop'),
    ('duckpond install-skills', 'give each agent a skill file so it knows duckpond and how to take a handoff'),
    ('duckpond doctor', 'check agents, stores, fzf and the cache'),
]


def table(rows, width):
    return '\n'.join(f'  {GREEN}{k:<{width}}{RESET} {v}' for k, v in rows)


def guide(color=True):
    out = [mini([f'{BOLD}duckpond{RESET}', TAGLINE, '', f'{DIM}don\'t feel like typing duckpond? aisp does exactly the same thing{RESET}']), '',
           f'{BOLD}What you are looking at{RESET}',
           '  Every session from Claude Code, Codex and Hermes on this machine, newest first.',
           '  The preview shows where it ran, what you asked and the last reply.',
           f'  A green {GREEN}●{RESET} means that session is open in another window right now.', '',
           f'{BOLD}Keys in the picker{RESET}', table(KEYS, 7), '',
           f'{BOLD}Handing off{RESET}',
           '  Ctrl-O writes the conversation to a private markdown file in the cache and starts the agent you pick',
           '  with an opening prompt that points at it. Hermes cannot take an opening prompt, so the prompt goes',
           '  on your clipboard instead.', '',
           f'{BOLD}From the shell{RESET}', table(COMMANDS, 32), '',
           f'{BOLD}Where things live{RESET}',
           '  cache     ~/.cache/duckpond        summaries, previews, handoff files; owner-only; safe to delete',
           '  settings  ~/.config/duckpond       config.ini: terminal command, pond boxes to hide',
           '  hidden    ~/.cache/duckpond/hidden.json', '',
           f'{DIM}Nothing leaves this machine. Agent stores are only ever read.{RESET}',
           f'{DIM}Standard library Python plus fzf, nothing else. Nothing runs in the background.{RESET}']
    text = '\n'.join(out)
    if not color:
        import re
        text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    return text
