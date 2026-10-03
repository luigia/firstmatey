import os, pathlib, subprocess, time, json, shutil, tempfile, hashlib, signal
ROOT=pathlib.Path.cwd()
E=pathlib.Path('/Users/luigi/.no-mistakes/evidence/01M407Y2945QQQ91DSKZSSDFMJ')
T=pathlib.Path(tempfile.mkdtemp(prefix='.refresh-live-',dir=ROOT))
HOME=T/'home'
results=[]
def run(label, command, env, timeout=90):
    start=time.monotonic()
    child=subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    try:
        out,err=child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGKILL)
        out,err=child.communicate()
        results.append({'label':label,'result':'setup timeout','wall_seconds':round(time.monotonic()-start,3)})
        raise
    p=subprocess.CompletedProcess(command,child.returncode,out,err)
    elapsed=time.monotonic()-start
    (E/(label+'.stdout')).write_bytes(p.stdout)
    (E/(label+'.stderr')).write_bytes(p.stderr)
    results.append({'command':command,'label':label,'exit':p.returncode,'wall_seconds':round(elapsed,3)})
    print(json.dumps(results[-1]),flush=True)
    assert p.returncode==0, label+': '+p.stderr.decode()
    return p.stdout, elapsed
try:
    run('create-lab',['bin/fm-lab-home.sh','create',str(HOME)],os.environ.copy())
    (HOME/'AGENTS.md').write_text('# Disposable summary validation home\n')
    (HOME/'.fm-secondmate-home').write_text('validation\n')
    (HOME/'data/backlog.md').write_text('## In flight\n\n## Queued\n\n## Done\n')
    env=os.environ.copy()
    for k in list(env):
        if k.startswith('FM_') or k in ('TASKS_AXI_FILE','TASKS_AXI_BACKEND'):
            env.pop(k)
    env.update(FM_HOME=str(HOME),FM_SNAPSHOT_NOW='2026-10-04T12:00:00Z',FM_SNAPSHOT_NOW_EPOCH='1791115200')
    def meta(i):
        id=f'mate-{i:02}'
        (HOME/'state'/f'{id}.meta').write_text(f'kind=secondmate\nmode=secondmate\nharness=claude\nworktree={HOME}\nhome={HOME}/child-{i}\n')
        return HOME/'state'/f'{id}.status'
    status=meta(1)
    status.write_text('needs-decision [key=buried]: pick REST or RPC\nblocked [key=old]: waiting on credentials\n'+('working: routine status observation filler\n'*5000))
    run('drain-5000',['bin/fm-wake-drain.sh'],env,180)
    cursor=HOME/'state/.mate-01.open-decisions-cursor'
    prior=cursor.read_bytes()
    with status.open('a') as f:
        f.write('resolved [key=old]: credentials arrived\nneeds-decision [key=tail]: choose rollout\n')
    _,small=run('refresh-5000',['bin/fm-home-summary-refresh.sh'],env)
    published=(HOME/'state/home-summary.json').read_bytes()
    (E/'published-5000.json').write_bytes(published)
    assert cursor.read_bytes()==prior,'refresh mutated wake cursor'
    doc=json.loads(published)
    assert [d['key'] for d in doc['decisions_open'] if d.get('source')=='status']==['buried','tail']
    # Invoke the original real producer with its original sibling implementations.
    baseline=T/'baseline'
    shutil.copytree(ROOT/'bin',baseline)
    for file in ['fm-classify-lib.sh','fm-crew-state.sh','fm-fleet-snapshot.sh']:
        p=subprocess.run(['git','show','e31bc6e620ca532c2e0e0b72f3fd7c0869a12270:bin/'+file],capture_output=True,check=True)
        (baseline/file).write_bytes(p.stdout)
    benv=env.copy(); benv['FM_ROOT_OVERRIDE']=str(ROOT)
    whole,_=run('baseline-5000',[str(baseline/'fm-fleet-snapshot.sh'),'--secondmate-home-summary'],benv,90)
    assert published==whole,'new publication differs from base producer'
    with status.open('a') as f: f.write('working: routine status observation filler\n'*10000)
    run('drain-15000',['bin/fm-wake-drain.sh'],env,180)
    _,large=run('refresh-15000',['bin/fm-home-summary-refresh.sh'],env)
    bigger=(HOME/'state/home-summary.json').read_bytes()
    (E/'published-15000.json').write_bytes(bigger)
    assert published==bigger,'history growth changed publication'
    assert large<30 and large<small+5, 'seeded refresh scales with covered history'
    whole,_=run('baseline-15000',[str(baseline/'fm-fleet-snapshot.sh'),'--secondmate-home-summary'],benv,90)
    assert whole==bigger,'grown publication differs from original producer'
    # Adversarial same-sized replacement must reject old inode's cursor.
    replaced=status.with_suffix('.new')
    replaced.write_text(status.read_text().replace('[key=buried]','[key=rename]'))
    replaced.replace(status)
    _,_=run('refresh-replaced',['bin/fm-home-summary-refresh.sh'],env)
    doc=json.loads((HOME/'state/home-summary.json').read_bytes())
    assert [d['key'] for d in doc['decisions_open'] if d.get('source')=='status']==['rename','tail']
    (E/'published-replaced.json').write_text(json.dumps(doc,indent=2))
    # Exercise real per-task prefetch and JSON assembly on a fleet-sized home.
    status.write_text('needs-decision [key=fleet-01]: choose rollout\n'+'working: routine observation\n'*60)
    for i in range(2,41):
        s=meta(i)
        s.write_text(f'needs-decision [key=fleet-{i:02}]: choose rollout\n'+'working: routine observation\n'*60)
    run('drain-fleet40',['bin/fm-wake-drain.sh'],env,180)
    _,fleet=run('refresh-fleet40',['bin/fm-home-summary-refresh.sh'],env)
    (E/'published-fleet40.json').write_bytes((HOME/'state/home-summary.json').read_bytes())
    assert fleet<60,'fleet-sized home exceeded unchanged deadline'
finally:
    (E/'live-refresh-results.json').write_text(json.dumps(results,indent=2))
    shutil.rmtree(T)
