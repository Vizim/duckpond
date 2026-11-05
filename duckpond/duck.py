"""The duck banner and tagline."""
GREEN, DIM, BOLD, RESET = '\033[38;5;41m', '\033[2m', '\033[1m', '\033[0m'
TAGLINE = 'all your AI sessions, one pond'

DUCK_ROWS = [
    '⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣤⣶⡿⠿⠿⢿⣶⣤⡀⠀⠀⠀⠀⠀⠀',
    '⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣰⣿⠋⠁⠀⠀⠀⠀⠈⠙⣿⣦⠀⠀⠀⠀⠀',
    '⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⠁⠀⠀⠀⠀⢴⠉⣢⠀⠈⣿⡷⠶⠶⠶⣶',
    '⠀⠀⢀⣤⣤⣀⠀⠀⠀⠀⠀⠀⣿⣿⠀⠀⠀⠀⠀⠈⠉⠁⠀⠀⢸⣿⠀⠀⢀⣿',
    '⠀⢠⣾⠟⠙⠻⣿⣦⡀⠀⠀⠀⢸⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣿⡇⢀⣠⡾⠃',
    '⢠⣿⠏⠀⠀⠀⠈⠻⣿⣤⣤⣤⣤⣿⣿⣄⠀⠀⠀⠀⠀⠀⢠⣾⡟⠛⠛⠉⠀⠀',
    '⣼⡿⠀⠀⠀⠀⠀⠀⠘⠛⠉⠉⠉⠉⠉⠉⠀⠀⠀⠀⠀⠀⠀⢻⣷⠀⠀⠀⠀⠀',
    '⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⣿⡇⠀⠀⠀⠀',
    '⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⡇⠀⠀⠀⠀',
    '⢻⣷⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣿⡇⠀⠀⠀⠀',
    '⠘⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⡿⠀⠀⠀⠀⠀',
    '⠀⠘⣿⣦⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣼⡿⠁⠀⠀⠀⠀⠀',
    '⠀⠀⠈⠙⠻⠿⣷⣶⣤⣤⣄⣀⣀⣀⣀⣀⣤⣤⣴⣶⡿⠿⠛⠀⠀⠀⠀⠀⠀⠀',
    '⠀⠀⠀⠀⠀⠀⠀⠈⠉⠉⠛⠛⠛⠛⠛⠛⠛⠉⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀',
]

MID_ROWS = [
    '⠀⠀⠀⠀⠀⠀⢠⡶⠟⠛⠻⢶⡄⠀⠀',
    '⠀⣀⣀⠀⠀⠀⣿⠁⠀⠸⠽⠈⣿⠛⣻',
    '⣰⡟⠙⢿⣆⣀⣻⣆⠀⠀⠀⣰⡿⠶⠋',
    '⣿⠀⠀⠀⠉⠉⠉⠉⠀⠀⠀⠸⣧⠀⠀',
    '⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣿⠀⠀',
    '⠹⣧⡀⠀⠀⠀⠀⠀⠀⠀⢀⣼⠇⠀⠀',
    '⠀⠉⠛⠻⠶⠶⠶⠶⠶⠟⠛⠁⠀⠀⠀',
]

MINI_ROWS = [
    '⠀⠀⠀⣰⠋⣙⢦⣤',
    '⡼⠙⢦⣽⠄⠀⣼⠚',
    '⣇⠀⠀⠀⠀⠀⣸⠀',
    '⠙⠦⣤⣤⣤⠴⠋⠀',
]


def mini(lines, color=True):
    # The small duck with up to four lines of text beside it.
    lines = list(lines) + [''] * (len(MINI_ROWS) - len(lines))
    out = []
    for row, text in zip(MINI_ROWS, lines):
        art = f'{GREEN}{row}{RESET}' if color else row
        out.append(f'{art}  {text}'.rstrip())
    return '\n'.join(out)


TEXT_ROWS = {
    4: f'{BOLD}duckpond{RESET}',
    5: TAGLINE,
    7: f'{DIM}one picker for every Claude Code, Codex{RESET}',
    8: f'{DIM}and Hermes session on this machine{RESET}',
}


def banner(color=True):
    lines = []
    for i, row in enumerate(DUCK_ROWS):
        art = f'{GREEN}{row}{RESET}' if color else row
        text = TEXT_ROWS.get(i, '')
        if not color:
            text = text.replace(BOLD, '').replace(DIM, '').replace(RESET, '')
        lines.append(f'  {art}   {text}'.rstrip())
    return '\n'.join(lines)


DUCK = banner()
