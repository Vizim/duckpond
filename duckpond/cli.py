"""The duckpond command: the picker by default, otherwise an indexer subcommand."""
import sys

from . import config, help as guide, launcher, picker, pond, sessions, skills
from .duck import DUCK

USAGE = sessions.USAGE


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
        print(guide.guide())
        if '--wait' in args:
            try:
                input('\npress Enter to go back ')
            except (EOFError, KeyboardInterrupt):
                pass
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
