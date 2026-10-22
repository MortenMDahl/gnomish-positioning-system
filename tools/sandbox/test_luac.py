"""The shipped Lua files against the game's Lua (5.1), which the sandbox's Lua 5.4 does not check.

Lua 5.1 refuses a file whose main chunk has more than 200 local variables alive at once, or a function
with more than 60 upvalues (outer local variables it reads). The sandbox runs Lua 5.4, whose limits are
higher, so every other test can pass while the game refuses GPS3D.lua. This test compiles every shipped
file (code and data) with luac5.1 and prints how close the code files are to both limits.

Run: python3 tools/sandbox/test_luac.py   (needs luac5.1: apt install lua5.1)
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
LUAC = shutil.which('luac5.1')
LOCALS, UPVALUES = 200, 60
results = []


def check(name, ok, detail=''):
    results.append(ok)
    print(('PASS ' if ok else 'FAIL ') + name + (' ' + detail if detail else ''))


def compile_ok(path):
    r = subprocess.run([LUAC, '-p', path], capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or r.stdout).strip()


def headroom(path):
    """Most locals alive at once in the main chunk, and the function with the most upvalues."""
    out = subprocess.run([LUAC, '-l', '-l', '-p', path], capture_output=True, text=True).stdout
    main_locals, worst = 0, (0, '')
    head = None
    in_main_locals = False
    spans = []
    for line in out.split('\n'):
        m = re.match(r'^(main|function) <([^>]*)> .*', line)
        if m:
            head = (m.group(1), m.group(2))
            continue
        m = re.match(r'^\d+\+? params?, \d+ slots?, (\d+) upvalues?, (\d+) locals?', line.strip())
        if m and head:
            if int(m.group(1)) > worst[0]:
                worst = (int(m.group(1)), head[1])
            continue
        if line.startswith('locals ('):
            in_main_locals = head is not None and head[0] == 'main'
            continue
        if line.startswith('upvalues (') or line.startswith('constants ('):
            in_main_locals = False
            continue
        if in_main_locals:
            parts = line.split()
            if len(parts) == 4:
                spans.append((int(parts[2]), int(parts[3])))
    if spans:
        events = sorted([(s, 1) for s, _ in spans] + [(e, -1) for _, e in spans], key=lambda t: (t[0], t[1]))
        alive = 0
        for _, d in events:
            alive += d
            main_locals = max(main_locals, alive)
    return main_locals, worst


if not LUAC:
    check('luac5.1 found (apt install lua5.1)', False)
    sys.exit(1)

code = sorted(glob.glob(os.path.join(ROOT, 'Interface/AddOns/GnomishPositioningSystem/*.lua')) + glob.glob(os.path.join(ROOT, 'prototypes/GPS3D/*.lua')))
data = sorted(glob.glob(os.path.join(ROOT, 'Interface/AddOns/GnomishPositioningSystem/Data/*.lua')) + glob.glob(os.path.join(ROOT, 'prototypes/GPS3D/Data/*.lua'))
              + glob.glob(os.path.join(ROOT, 'prototypes/GPS3D_*/*.lua')))  # (the load-on-demand data addons, since 2026-10-22)
bad = [(os.path.relpath(p, ROOT), msg) for p in code + data for ok, msg in [compile_ok(p)] if not ok]
check(f'every shipped file compiles with Lua 5.1 ({len(code)} code files, {len(data)} data files)', not bad and len(code) >= 8, str(bad[:3]))

lines = []
tight = []
for p in code:
    loc, (up, where) = headroom(p)
    where = os.path.relpath(where.split(':')[0], ROOT) + ':' + where.split(':', 1)[1] if ':' in where else where
    name = os.path.relpath(p, ROOT)
    lines.append(f'{name}: main chunk {loc}/{LOCALS} locals alive at once, most upvalues {up}/{UPVALUES} ({where})')
    if loc > LOCALS or up > UPVALUES:
        tight.append(name)
print('\n'.join('     ' + l for l in lines))
check('within Lua 5.1 limits (200 locals in a main chunk, 60 upvalues in a function); headroom above', not tight, str(tight))

# the compiler really refuses a function with 61 upvalues (what this test is here to catch)
with tempfile.NamedTemporaryFile('w', suffix='.lua', delete=False) as f:
    names = [f'u{i}' for i in range(61)]
    f.write(''.join(f'local {n} = {i}\n' for i, n in enumerate(names)))
    f.write('local function F() return ' + ' + '.join(names) + ' end\n')
    probe = f.name
ok, msg = compile_ok(probe)
os.unlink(probe)
check('a function with 61 upvalues is refused by luac5.1 (the limit this test guards)', not ok and 'upvalue' in msg, msg)

print(f'{sum(results)} of {len(results)} checks passed')
sys.exit(0 if all(results) else 1)
