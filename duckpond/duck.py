"""The duck. You talk to it when your code is broken; duckpond finds the duck you were talking to."""
YELLOW, ORANGE, DIM, BOLD, RESET = '\033[38;5;220m', '\033[38;5;208m', '\033[2m', '\033[1m', '\033[0m'

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

TEXT_ROWS = {
    4: f'{BOLD}duckpond{RESET}',
    5: 'get back to the duck you were talking to',
    7: f'{DIM}one picker for every Claude Code, Codex{RESET}',
    8: f'{DIM}and Hermes session on this machine{RESET}',
}


def banner(color=True):
    lines = []
    for i, row in enumerate(DUCK_ROWS):
        art = f'{YELLOW}{row}{RESET}' if color else row
        text = TEXT_ROWS.get(i, '')
        if not color:
            text = text.replace(BOLD, '').replace(DIM, '').replace(RESET, '')
        lines.append(f'  {art}   {text}'.rstrip())
    return '\n'.join(lines)


DUCK = banner()
