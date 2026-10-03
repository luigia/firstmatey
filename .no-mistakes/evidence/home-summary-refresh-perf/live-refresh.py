import os, pathlib, subprocess, time, json, shutil
root = pathlib.Path.cwd()
evidence = pathlib.Path('/Users/luigi/.no-mistakes/evidence/01M40XNNXBW3XW8EWKNWVK61ST')
home = root / '.test-tmp/live-home'
home.mkdir()
for d in ['state','data','config','projects']:
    (home/d).mkdir()
(home/'AGENTS.md').write_text('# Isolated summary validation home\n')
(home/'.fm-secondmate-home').write_text('summary-validation\n')
(home/'data/backlog.md').write_text('## In flight\n\n## Queued\n\n## Done\n')
env = {k:v for k,v in os.environ.items() if k not in ['FM_STATE_OVERRIDE','FM_CONFIG_OVERRIDE','FM_DATA_OVERRIDE','FM_PROJECTS_OVERRIDE','FM_CLASSIFY_RESERVED_KEY_PREFIXES','FM_CLASSIFY_RESOLVE_VERB','FM_CLASSIFY_CAPTAIN_HELD_VERB','FM_HOME_SUMMARY_TIMEOUT']}
env.update(FM_HOME=str(home), FM_ROOT_OVERRIDE=str(root), FM_STATE_OVERRIDE=str(home/'state'), FM_CONFIG_OVERRIDE=str(home/'config'), FM_DATA_OVERRIDE=str(home/'data'), FM_PROJECTS_OVERRIDE=str(home/'projects'), TMPDIR=str(root/'.test-tmp'), FM_SNAPSHOT_NOW='2026-10-02T12:00:00Z', FM_SNAPSHOT_NOW_EPOCH='1790942400')
log = []
def run(script, args=(), extra=None, artifact=None, timeout=180):
    start=time.monotonic()
    proc=subprocess.run([str(root/'bin'/script), *args], env=env | (extra or {}), capture_output=True, timeout=timeout)
    elapsed=time.monotonic()-start
    if artifact:
        (evidence/artifact).write_bytes(proc.stdout)
    assert proc.returncode == 0, (script, proc.returncode, proc.stderr.decode())
    return proc.stdout, elapsed

def refresh(label, extra=None):
    before={p.name:(p.read_bytes() if p.is_file() else b'<directory>') for p in (home/'state').glob('*.open-decisions-cursor')}
    _,elapsed=run('fm-home-summary-refresh.sh',extra=extra,timeout=65)
    after={p.name:(p.read_bytes() if p.is_file() else b'<directory>') for p in (home/'state').glob('*.open-decisions-cursor')}
    assert before == after, 'refresh mutated wake-drain cursor'
    data=(home/'state/home-summary.json').read_bytes()
    (evidence/(label+'.json')).write_bytes(data)
    parsed=json.loads(data)
    keys=[d['key'] for d in parsed['decisions_open'] if d.get('source')=='status']
    log.append(dict(scenario=label,seconds=round(elapsed,3),decision_keys=keys,cursors_unchanged=True))
    return data,keys

try:
    for i in range(6):
        (home/f'state/mate-{i}.meta').write_text(f'kind=secondmate\nmode=secondmate\nharness=claude\nwindow=fm-lab-summary:missing-{i}\nhome={home}/projects/mate-{i}\n')
        (home/f'state/mate-{i}.status').write_text(f'needs-decision [key=choice-{i}]: choose rollout\nblocked [key=old-{i}]: credentials\n'+'working: routine long-history progress\n'*100)
    run('fm-wake-drain.sh',artifact='live-drain-small.txt')
    for i in range(6):
        with (home/f'state/mate-{i}.status').open('a') as f:
            f.write(f'resolved [key=old-{i}]: received\nneeds-decision [key=tail-{i}]: choose window\n')
    small, keys = refresh('live-small-seeded')
    assert set(keys)=={f'{prefix}-{i}' for prefix in ['choice','tail'] for i in range(6)}
    cursors={p:p.read_bytes() for p in (home/'state').glob('*.open-decisions-cursor')}
    for p in cursors: p.unlink()
    whole,_=refresh('live-small-whole')
    assert whole==small,'seeded publication differs from whole-log publication'
    for p,b in cursors.items(): p.write_bytes(b)
    for i in range(6):
        with (home/f'state/mate-{i}.status').open('a') as f: f.write('working: routine long-history progress\n'*1900)
    run('fm-wake-drain.sh',artifact='live-drain-large.txt',timeout=300)
    for i in range(6):
        with (home/f'state/mate-{i}.status').open('a') as f: f.write(f'needs-decision [key=new-{i}]: choose final window\n')
    large,keys=refresh('live-large-seeded')
    assert set(keys)=={f'{prefix}-{i}' for prefix in ['choice','tail','new'] for i in range(6)}
    cursors={p:p.read_bytes() for p in (home/'state').glob('*.open-decisions-cursor')}
    for p in cursors: p.unlink()
    large_whole,_=refresh('live-large-whole')
    assert large_whole==large
    for p,b in cursors.items(): p.write_bytes(b)
    # Force invalid captures without intercepting cp or any product dependency.
    for kind in ['corrupt','directory','symlink']:
        for p,b in cursors.items():
            p.unlink()
            if kind=='corrupt': p.write_text('version=invalid\noffset=99999999\nident=wrong\n')
            elif kind=='directory': p.mkdir()
            else: p.symlink_to(home/'AGENTS.md')
        actual,_=refresh('live-'+kind+'-cursor')
        assert actual==large
        for p in cursors:
            if p.is_dir() and not p.is_symlink(): p.rmdir()
            else: p.unlink()
            p.write_bytes(cursors[p])
    # Configuration adversaries use short, new logs to avoid expensive drain setup.
    for i in range(6):
        (home/f'state/mate-{i}.status').write_text(f'needs-decision [key=config-{i}]: choose configuration\n')
    # Prefix mismatch must recover the decision previously excluded by the drain.
    f=home/'state/mate-0.status'
    with f.open('a') as out: out.write('needs-decision [key=secret-choice]: choose transport\n')
    run('fm-wake-drain.sh',extra={'FM_CLASSIFY_RESERVED_KEY_PREFIXES':'pending-reply- secret-'},artifact='live-custom-prefix-drain.txt',timeout=300)
    _,keys=refresh('live-prefix-mismatch')
    assert 'secret-choice' in keys
    _,keys=refresh('live-custom-prefix',{'FM_CLASSIFY_RESERVED_KEY_PREFIXES':'pending-reply- secret-'})
    assert 'secret-choice' not in keys
    # Resolve/held changes must recover open decisions from a differently configured cursor.
    with f.open('a') as out: out.write('needs-decision [key=resolved-choice]: choose\nresolved [key=resolved-choice]: closed\nneeds-decision [key=held-choice]: choose\ncaptain-held [key=held-choice]: retained\n')
    run('fm-wake-drain.sh',artifact='live-default-verbs-drain.txt',timeout=300)
    _,keys=refresh('live-verb-mismatch',{'FM_CLASSIFY_RESOLVE_VERB':'settled','FM_CLASSIFY_CAPTAIN_HELD_VERB':'parked'})
    assert 'resolved-choice' in keys and 'held-choice' in keys
    # Replace one log at the same path; the old cursor must not seed it.
    replaced=f.with_suffix('.new')
    replaced.write_text('needs-decision [key=replacement-choice]: new log\n')
    replaced.replace(f)
    _,keys=refresh('live-replaced-log')
    assert 'replacement-choice' in keys and 'choice-0' not in keys
    log.append({'result':'All live publication assertions passed','tasks':6,'small_history_lines_per_task':100,'large_history_lines_per_task':2000,'deadline_seconds':60,'dependencies':'real product executables; no stubs or live fleet endpoints'})
finally:
    (evidence/'live-refresh-results.json').write_text(json.dumps(log,indent=2)+'\n')
    shutil.rmtree(home)
print(json.dumps(log,indent=2))
