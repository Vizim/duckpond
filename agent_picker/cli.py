"""The aisp command: the picker by default, otherwise an indexer subcommand."""
import sys

from . import launcher, picker, sessions

USAGE = sessions.USAGE


def version():
    try:
        from importlib.metadata import version as v
        return v('ai-session-picker')
    except Exception:
        return 'dev'


def main():
    args = sys.argv[1:]
    if not args:
        return picker.main()
    if args == ['--window']:
        return picker.open_window()
    if args[0] in ('-h', '--help', 'help'):
        print(USAGE)
        return
    if args[0] in ('-V', '--version'):
        print(f'aisp {version()}')
        return
    if args == ['install-launcher']:
        print(launcher.install())
        return
    return sessions.main(args)


if __name__ == '__main__':
    main()
