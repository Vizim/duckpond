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

from . import sessions

USAGE = """agent-picker            run the picker in this terminal
agent-picker --window   open the picker in a new terminal window"""

HEADER = 'Enter resume | C-F fork | C-O hand off to another agent | C-N new here | C-T cloud here | C-X hide | C-U unhide all | C-Y copy id | C-R refresh'

# Fork and cloud sessions exist only for claude; other agents fall back to resume or new.
COMMANDS = {
    'claude': dict(new=['claude'], resume=['claude', '--resume', '{sid}'],
                   fork=['claude', '--resume', '{sid}', '--fork-session'], cloud=['claude', '--teleport']),
    'codex': dict(new=['codex'], resume=['codex', 'resume', '{sid}']),
    'hermes': dict(new=['hermes', 'chat'], resume=['hermes', '--resume', '{sid}']),
}


def indexer():
    # Returns the argv list and the same command as a string for fzf bindings.
    exe = shutil.which('agent-sessions')
    if exe:
        return ['agent-sessions'], 'agent-sessions'
    return [sys.executable, '-m', 'agent_picker.sessions'], f'"{sys.executable}" -m agent_picker.sessions'


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def snapshot():
    out = []
    for p in sessions.watched_files():
        try:
            st = os.stat(p)
            out.append((p, st.st_mtime, st.st_size))
        except OSError:
            pass
    return tuple(out)


def watch(proc, port, key, idx):
    # Push a reload to fzf whenever a session store changes, while fzf lives.
    seen = None
    while proc.poll() is None:
        now = snapshot()
        if seen is not None and now != seen:
            req = urllib.request.Request(f'http://127.0.0.1:{port}', data=f'reload({idx} {{q}})'.encode(),
                                         headers={'x-api-key': key}, method='POST')
            try:
                urllib.request.urlopen(req, timeout=2).close()
            except OSError:
                pass
        seen = now
        time.sleep(2)


def pick():
    if not shutil.which('fzf'):
        sys.exit('agent-picker: fzf not found, see https://github.com/junegunn/fzf#installation')
    idx_argv, idx = indexer()
    key, port = secrets.token_hex(16), free_port()
    env = dict(os.environ, FZF_API_KEY=key, AGENT_PICKER_CACHE=sessions.CACHE)
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env['PYTHONPATH'] = pkg_root + os.pathsep + env.get('PYTHONPATH', '')
    initial = subprocess.run(idx_argv, capture_output=True, env=env).stdout
    fzf = ['fzf', '--delimiter=\t', '--with-nth=4', '--ansi', '--reverse', '--height=100%', '--disabled',
           '--prompt=sessions > ', '--expect=ctrl-n,ctrl-t,ctrl-f,ctrl-o', f'--listen=127.0.0.1:{port}', '--track',
           f'--bind=change:reload({idx} {{q}})', f'--bind=ctrl-r:reload({idx} {{q}})',
           f'--bind=ctrl-x:execute-silent({idx} --hide {{1}} {{2}})+reload({idx} {{q}})',
           f'--bind=ctrl-u:execute-silent({idx} --unhide-all)+reload({idx} {{q}})',
           f'--bind=ctrl-y:execute-silent({idx} --copy {{2}})',
           f'--header={HEADER}', f'--preview={idx} --preview {{1}} {{2}}',
           '--preview-window=right,50%,wrap,<110(down,45%,wrap)']
    proc = subprocess.Popen(fzf, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env)
    threading.Thread(target=watch, args=(proc, port, key, idx), daemon=True).start()
    out, _ = proc.communicate(initial)
    lines = out.decode('utf-8', 'replace').splitlines()
    if len(lines) < 2 or not lines[1].strip():
        return
    pressed, sel = lines[0], lines[1]
    agent, sid, where = (sel.split('\t') + ['', '', ''])[:3]
    try:
        os.chdir(where)
    except OSError:
        os.chdir(os.path.expanduser('~'))
    spec = COMMANDS.get(agent, COMMANDS['claude'])
    if pressed == 'ctrl-n' or sid == '__NEW__' or (pressed == 'ctrl-f' and sid.startswith('__')):
        cmd = spec['new']
    elif pressed == 'ctrl-t':
        cmd = spec.get('cloud') or spec['new']
    elif sid == '__CLOUD__':
        cmd = cloud_by_link()
    elif pressed == 'ctrl-f':
        cmd = spec.get('fork') or spec['resume']
    elif pressed == 'ctrl-o' and not sid.startswith('__'):
        cmd = handoff(agent, sid, idx_argv, env)
    else:
        cmd = spec['resume']
    launch([c.replace('{sid}', sid) for c in cmd])


def handoff(agent, sid, idx_argv, env):
    # Export the conversation to a private file and open another agent on it in the same directory.
    targets = [a for a in sessions.installed() if a != agent]
    if not targets:
        sys.exit('agent-picker: no other agent installed')
    menu = subprocess.run(['fzf', '--reverse', '--height=100%', '--prompt=hand off to > ', '--no-info'],
                          input='\n'.join(targets).encode(), stdout=subprocess.PIPE)
    target = menu.stdout.decode().strip()
    if target not in targets:
        sys.exit(0)
    out = os.path.join(sessions.CACHE, f'handoff-{agent}-{sid}.md')
    if subprocess.run(idx_argv + ['--export', agent, sid, out], env=env).returncode != 0:
        sys.exit('agent-picker: export failed')
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
        sys.exit(f'agent-picker: {cmd[0]} not found')
    if sys.platform == 'win32':
        sys.exit(subprocess.call([exe] + cmd[1:]))
    os.execv(exe, cmd)


def self_argv():
    exe = shutil.which('agent-picker')
    return [exe] if exe else [sys.executable, '-m', 'agent_picker.picker']


def open_window():
    me = self_argv()
    custom = os.environ.get('AGENT_PICKER_TERMINAL')
    if custom:
        argv = shlex.split(custom) + me
    elif sys.platform == 'darwin':
        script = f'tell application "Terminal" to do script "{shlex.join(me)}"'
        argv = ['osascript', '-e', script, '-e', 'tell application "Terminal" to activate']
    elif sys.platform == 'win32':
        argv = ['wt'] + me if shutil.which('wt') else ['cmd', '/c', 'start', ''] + me
    else:
        terminals = [('kitty', ['-e']), ('alacritty', ['-e']), ('foot', []), ('wezterm', ['start', '--']),
                     ('gnome-terminal', ['--']), ('konsole', ['-e']), ('xfce4-terminal', ['-x']), ('xterm', ['-e'])]
        argv = None
        for name, flag in terminals:
            if shutil.which(name):
                argv = [name] + flag + me
                break
        if not argv:
            sys.exit('agent-picker: no terminal found, set AGENT_PICKER_TERMINAL')
    kwargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if sys.platform != 'win32':
        kwargs['start_new_session'] = True
    subprocess.Popen(argv, **kwargs)


def main():
    os.umask(0o077)
    args = sys.argv[1:]
    if not args:
        pick()
    elif args == ['--window']:
        open_window()
    elif args in (['-h'], ['--help']):
        print(USAGE)
    else:
        sys.exit(f'usage: {USAGE}')


if __name__ == '__main__':
    main()
