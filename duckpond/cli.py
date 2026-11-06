"""The duckpond command: the picker by default, otherwise an indexer subcommand."""
import sys

from . import config, help as guide, launcher, picker, pond, sessions, skills
from .duck import DUCK

USAGE = sessions.USAGE


def terminal():
    # fzf gives executed commands its own stdout, which is a pipe under the picker, so talk to the terminal directly.
    try:
        if sys.platform == 'win32':
            return open('CONOUT$', 'w', encoding='utf-8'), open('CONIN$', 'r', encoding='utf-8')
        return open('/dev/tty', 'w', encoding='utf-8'), open('/dev/tty', 'r', encoding='utf-8')
    except OSError:
        return sys.stdout, sys.stdin


def ask(question, then):
    # A y/n prompt on the terminal itself, for actions the picker should not do by accident.
    out, inp = terminal()
    out.write(f'\n{question} [y/N] ')
    out.flush()
    try:
        answer = inp.readline().strip().lower()
    except (OSError, KeyboardInterrupt):
        answer = ''
    if answer in ('y', 'yes'):
        sessions.main(then)
        out.write('done\n')
    else:
        out.write('left alone\n')
    out.flush()


def show_help_page():
    out, inp = terminal()
    out.write('\033[H\033[2J' + guide.guide() + '\n\npress Enter to go back ')
    out.flush()
    try:
        inp.readline()
    except (OSError, KeyboardInterrupt):
        pass


def version():
    try:
        from importlib.metadata import version as v
        return v('duckpond')
    except Exception:
        return 'dev'


def main():
    args = sys.argv[1:]
    if not args:
        return picker.main()
    if args == ['--window']:
        return picker.open_window()
    if args[0] == 'help':
        if '--wait' in args:
            return show_help_page()
        print(guide.guide())
        return
    if args[0] in ('-h', '--help'):
        print(DUCK)
        print(USAGE)
        print('\nduckpond help    the full guide: keys, handoff, where things live')
        return
    if args[0] in ('-V', '--version'):
        print(f'duckpond {version()}')
        return
    if args == ['install-launcher']:
        print(launcher.install())
        return
    if args == ['uninstall-launcher']:
        print(launcher.uninstall())
        return
    if args[0] == 'install-skills':
        print(skills.install(args[1:] or None))
        return
    if args == ['uninstall-skills']:
        print(skills.uninstall())
        return
    if args[0] == 'pond':
        return pond.run(args[1:])
    if args[:1] == ['ask'] and len(args) >= 2:
        questions = {'hide-all': 'Hide every session from the list? They stay on disk and Ctrl-U brings them back.',
                     'rebuild': 'Rebuild the index from scratch? The next listing rescans every transcript.'}
        if args[1] in questions:
            return ask(questions[args[1]], args[1:])
        sys.exit('usage: duckpond ask hide-all|rebuild')
    if args == ['vscode-windows']:
        windows, names = sessions.refresh_vscode_windows()
        print(f"{windows} window{'s' if windows != 1 else ''}: {', '.join(sorted(names)) or 'none'}")
        return
    if args[0] == 'last':
        row = sessions.newest(args[1:])
        if not row:
            sys.exit('duckpond: no session matches' if args[1:] else 'duckpond: no sessions yet')
        _, agent, sid, where, d, _ = row
        return picker.go(agent, sid, where, sessions.title(d))
    if args[0] == 'config':
        if len(args) == 1:
            print(config.show())
        elif len(args) in (2, 3):
            config.set_value(args[1], args[2] if len(args) == 3 else '')
            print(config.show())
        else:
            sys.exit('usage: duckpond config [KEY [VALUE]]')
        return
    return sessions.main(args)


if __name__ == '__main__':
    main()
