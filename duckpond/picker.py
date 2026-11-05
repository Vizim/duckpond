"""Pick a recent Claude Code, Codex or Hermes session with fzf and resume it."""
import os
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request

from . import config, sessions
from .duck import BOLD, DIM, GREEN, RESET, TAGLINE, mini

def header(rows):
    # Beside the mini duck: name and tagline, what is listed, and where help lives.
    real = [r for r in rows if r.split('\t')[1:2] and not r.split('\t')[1].startswith('__')]
    agents = sorted({r.split('\t')[0] for r in real})
    if real:
        status = f'{len(real)} session{"s" if len(real) != 1 else ""} from {", ".join(agents)}'
    else:
        status = 'no sessions yet. run claude, codex or hermes once and it will show up here'
    return mini([f'{BOLD}duckpond{RESET}  {DIM}{TAGLINE}{RESET}', f'{DIM}{status}{RESET}', '',
                 f'Have a question? Hit {BOLD}F1{RESET} for the help menu.'])


# fzf colours: pond green for the frame and pointer, agent colours stay inside the rows.
THEME = 'fg:#d4d4d8,bg:-1,hl:#22c55e,fg+:#fafafa,bg+:#1f1f28,hl+:#86efac,prompt:#22c55e,pointer:#22c55e,'\
        'header:#71717a,info:#71717a,border:#3f3f46,label:#22c55e,preview-border:#3f3f46'

# Fork and cloud sessions exist only for claude; other agents fall back to resume or new.
COMMANDS = {
    'claude': dict(new=['claude'], resume=['claude', '--resume', '{sid}'],
                   fork=['claude', '--resume', '{sid}', '--fork-session'], cloud=['claude', '--teleport']),
    'codex': dict(new=['codex'], resume=['codex', 'resume', '{sid}']),
    'hermes': dict(new=['hermes', 'chat'], resume=['hermes', '--resume', '{sid}']),
}


def self_command():
    # Returns argv for this program and the same command as a string for fzf bindings.
    exe = shutil.which('duckpond') or shutil.which('aisp')
    if exe:
        return [exe], os.path.basename(exe).replace('.exe', '')
    return [sys.executable, '-m', 'duckpond.cli'], f'"{sys.executable}" -m duckpond.cli'


def decide(pressed, agent, sid):
    # Maps the fzf key and row to an action; cloud and fork exist only for claude.
    if pressed == 'ctrl-n' or sid == '__NEW__' or (pressed == 'ctrl-f' and sid.startswith('__')):
        return 'new'
    if pressed == 'ctrl-t':
        return 'cloud' if agent == 'claude' else 'new'
    if sid == '__CLOUD__':
        return 'cloud-link'
    if pressed == 'ctrl-f':
        return 'fork' if agent == 'claude' else 'resume'
    if pressed == 'ctrl-o' and not sid.startswith('__'):
        return 'handoff'
    return 'resume'


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


ANSI = re.compile(r'\x1b\[[0-9;]*m')


def signature(rows):
    # What the list looks like, minus the clock: a reload is only worth the blink when this changes.
    out = []
    for row in rows:
        parts = row.split('\t')
        if len(parts) < 4:
            continue
        label = ANSI.sub('', parts[3])
        out.append((parts[0], parts[1], parts[2], label[:1], label[13:]))
    return tuple(out)


def watch(proc, port, key, me, me_argv, env):
    # Re-list every two seconds and push a reload to fzf only when rows, titles, order or live marks change.
    seen = None
    while proc.poll() is None:
        try:
            rows = subprocess.run(me_argv + ['list'], capture_output=True, env=env, timeout=30).stdout
        except (OSError, subprocess.SubprocessError):
            rows = b''
        now = signature(rows.decode('utf-8', 'replace').splitlines())
        if seen is not None and now != seen:
            req = urllib.request.Request(f'http://127.0.0.1:{port}', data=f'reload({me} list {{q}})'.encode(),
                                         headers={'x-api-key': key}, method='POST')
            try:
                urllib.request.urlopen(req, timeout=2).close()
            except OSError:
                pass
        seen = now
        time.sleep(2)


def pick():
    if not shutil.which('fzf'):
        sys.exit('duckpond: fzf not found, see https://github.com/junegunn/fzf#installation')
    me_argv, me = self_command()
    key, port = secrets.token_hex(16), free_port()
    env = dict(os.environ, FZF_API_KEY=key, DUCKPOND_CACHE=sessions.CACHE)
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env['PYTHONPATH'] = pkg_root + os.pathsep + env.get('PYTHONPATH', '')
    initial = subprocess.run(me_argv + ['list'], capture_output=True, env=env).stdout
    head = header(initial.decode('utf-8', 'replace').splitlines())
    fzf = ['fzf', '--delimiter=\t', '--with-nth=4', '--ansi', '--reverse', '--height=100%', '--disabled',
           '--prompt=sessions › ', '--pointer=▶', '--border=rounded', '--border-label= duckpond ', '--border-label-pos=3',
           f'--color={THEME}', '--expect=ctrl-n,ctrl-t,ctrl-f,ctrl-o', f'--listen=127.0.0.1:{port}', '--track',
           f'--bind=change:reload({me} list {{q}})', f'--bind=ctrl-r:reload({me} list {{q}})',
           f'--bind=ctrl-x:execute-silent({me} hide {{1}} {{2}})+reload({me} list {{q}})',
           f'--bind=ctrl-u:execute-silent({me} unhide-all)+reload({me} list {{q}})',
           f'--bind=ctrl-y:execute-silent({me} copy {{2}})',
           f'--bind=ctrl-p:change-preview({me} preview --full {{1}} {{2}})',
           f'--bind=focus:change-preview({me} preview {{1}} {{2}})',
           f'--bind=f1:change-preview({me} help)',
           f'--header={head}', f'--preview={me} preview {{1}} {{2}}',
           '--preview-window=right,50%,wrap,<110(down,45%,wrap)']
    proc = subprocess.Popen(fzf, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env)
    threading.Thread(target=watch, args=(proc, port, key, me, me_argv, env), daemon=True).start()
    out, _ = proc.communicate(initial)
    lines = out.decode('utf-8', 'replace').splitlines()
    if len(lines) < 2 or not lines[1].strip():
        return
    pressed, sel = lines[0], lines[1]
    agent, sid, where, label = (sel.split('\t') + ['', '', '', ''])[:4]
    try:
        os.chdir(where)
    except OSError:
        os.chdir(os.path.expanduser('~'))
    spec = COMMANDS.get(agent, COMMANDS['claude'])
    action = decide(pressed, agent, sid)
    if action == 'cloud-link':
        cmd = cloud_by_link()
    elif action == 'handoff':
        cmd = handoff(agent, sid, me_argv, env)
    else:
        cmd = spec[action]
    if action in ('resume', 'fork'):
        title = re.split(r'\s{2,}', re.sub(r'\x1b\[[0-9;]*m', '', label).strip())[-1]
        print(f"{GREEN}\u25b6{RESET} back to {BOLD}{title}{RESET}  {DIM}{agent} \u00b7 {os.path.basename(where.rstrip(os.sep)) or where}{RESET}")
    launch([c.replace('{sid}', sid) for c in cmd])


def handoff(agent, sid, me_argv, env):
    # Export the conversation to a private file and open another agent on it in the same directory.
    targets = [a for a in sessions.installed() if a != agent]
    if not targets:
        sys.exit('duckpond: no other agent installed')
    menu = subprocess.run(['fzf', '--reverse', '--height=100%', '--prompt=hand off to > ', '--no-info'],
                          input='\n'.join(targets).encode(), stdout=subprocess.PIPE)
    target = menu.stdout.decode().strip()
    if target not in targets:
        sys.exit(0)
    out = os.path.join(sessions.CACHE, f'handoff-{agent}-{sid}.md')
    if subprocess.run(me_argv + ['export', agent, sid, out], env=env).returncode != 0:
        sys.exit('duckpond: export failed')
    prompt = (f'You are taking over from a {agent} session. Read {out} for the full conversation so far, '
              f'then continue from where it left off.')
    if target == 'hermes':
        sessions.copy_text(prompt)
        print(f'Handoff written to {out}\nThe opening prompt is on your clipboard, paste it into hermes.\n')
        return COMMANDS['hermes']['new']
    return COMMANDS[target]['new'] + [prompt]


def cloud_by_link():
    link = input('claude.ai/code link or session id: ')
    m = re.search(r'session_[A-Za-z0-9]+', link)
    if not m:
        sys.exit('no session id in that')
    return ['claude', '--teleport', m.group(0)]


def launch(cmd):
    exe = shutil.which(cmd[0])
    if not exe:
        sys.exit(f'duckpond: {cmd[0]} not found')
    if sys.platform == 'win32':
        sys.exit(subprocess.call([exe] + cmd[1:]))
    os.execv(exe, cmd)


def window_argv(me, platform=sys.platform, custom=None, which=shutil.which):
    # The terminal setting is a command prefix; {cmd} marks where the program goes if not at the end.
    if custom:
        parts = shlex.split(custom)
        if '{cmd}' in parts:
            i = parts.index('{cmd}')
            return parts[:i] + me + parts[i + 1:]
        return parts + me
    if platform == 'darwin':
        script = f'tell application "Terminal" to do script "{shlex.join(me)}"'
        return ['osascript', '-e', script, '-e', 'tell application "Terminal" to activate']
    if platform == 'win32':
        return ['wt'] + me if which('wt') else ['cmd', '/c', 'start', ''] + me
    terminals = [('kitty', ['-e']), ('alacritty', ['-e']), ('foot', []), ('wezterm', ['start', '--']),
                 ('ghostty', ['-e']), ('gnome-terminal', ['--']), ('konsole', ['-e']), ('xfce4-terminal', ['-x']),
                 ('xterm', ['-e'])]
    for name, flag in terminals:
        if which(name):
            return [name] + flag + me
    return None


def open_window():
    argv = window_argv(self_command()[0], custom=config.get('terminal'))
    if not argv:
        sys.exit('duckpond: no terminal found, set one with: duckpond config terminal "alacritty -e"')
    kwargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if sys.platform != 'win32':
        kwargs['start_new_session'] = True
    subprocess.Popen(argv, **kwargs)


def main():
    os.umask(0o077)
    pick()


if __name__ == '__main__':
    main()
