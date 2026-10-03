import pathlib, tempfile, subprocess, os, time, json, shutil, signal
R=pathlib.Path.cwd(); E=pathlib.Path('/Users/luigi/.no-mistakes/evidence/01M407Y2945QQQ91DSKZSSDFMJ')
T=pathlib.Path(tempfile.mkdtemp(prefix='.refresh-wide-',dir=R)); H=T/'home'; results=[]
def run(label,cmd,env,timeout=180):
    p=subprocess.Popen(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True); start=time.monotonic()
    try: out,err=p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGKILL); out,err=p.communicate(); raise
    item={'label':label,'command':cmd,'exit':p.returncode,'seconds':round(time.monotonic()-start,3)}; results.append(item); print(json.dumps(item),flush=True)
    (E/(label+'.stdout')).write_bytes(out); (E/(label+'.stderr')).write_bytes(err)
    return p.returncode,out
try:
    assert run('wide-create',['bin/fm-lab-home.sh','create',str(H)],os.environ.copy())[0]==0
    env={k:v for k,v in os.environ.items() if not k.startswith('FM_') and k not in ('TASKS_AXI_FILE','TASKS_AXI_BACKEND')}
    env.update(FM_HOME=str(H),FM_SNAPSHOT_NOW='2026-10-04T12:00:00Z',FM_SNAPSHOT_NOW_EPOCH='1791115200')
    (H/'AGENTS.md').write_text('# Wide accumulated history validation\n'); (H/'.fm-secondmate-home').write_text('wide\n')
    (H/'data/backlog.md').write_text('## In flight\n\n## Queued\n\n## Done\n')
    (H/'state/wide.meta').write_text(f'kind=secondmate\nmode=secondmate\nharness=claude\nworktree={H}\nhome={H}/child\n')
    s=H/'state/wide.status'
    s.write_text('needs-decision [key=buried]: decide transport\n'+('working: '+('validation reported on the branch after review '*50)+'\n')*5000)
    assert run('wide-drain',['bin/fm-wake-drain.sh'],env,240)[0]==0
    c=H/'state/.wide.open-decisions-cursor'; before=c.read_bytes()
    with s.open('a') as f: f.write('needs-decision [key=tail]: decide deployment\n')
    assert run('wide-refresh',['bin/fm-home-summary-refresh.sh'],env)[0]==0
    original=(H/'state/home-summary.json').read_bytes(); (E/'published-wide.json').write_bytes(original)
    assert [d['key'] for d in json.loads(original)['decisions_open'] if d.get('source')=='status']==['buried','tail']
    assert before==c.read_bytes()
    b=T/'baseline'; shutil.copytree(R/'bin',b)
    for name in ['fm-classify-lib.sh','fm-crew-state.sh','fm-fleet-snapshot.sh']:
        (b/name).write_bytes(subprocess.run(['git','show','e31bc6e620ca532c2e0e0b72f3fd7c0869a12270:bin/'+name],capture_output=True,check=True).stdout)
    benv=env.copy(); benv['FM_ROOT_OVERRIDE']=str(R)
    rc,_=run('wide-base-refresh',[str(b/'fm-home-summary-refresh.sh')],benv,75)
    if rc==0: assert (H/'state/home-summary.json').read_bytes()==original
    else: assert rc==124, 'unexpected original refresh failure'
    # Invalid cursor must fall back rather than publish fabricated open records.
    s.write_text('needs-decision [key=current]: a replacement log\n')
    c.write_text('version=bogus\noffset=999999999\nident=bogus\nfake\tneeds-decision\tnot real\n')
    assert run('invalid-cursor-refresh',['bin/fm-home-summary-refresh.sh'],env)[0]==0
    doc=(H/'state/home-summary.json').read_bytes(); (E/'published-invalid-cursor.json').write_bytes(doc)
    assert [d['key'] for d in json.loads(doc)['decisions_open'] if d.get('source')=='status']==['current']
    c.unlink()
    assert run('missing-cursor-refresh',['bin/fm-home-summary-refresh.sh'],env)[0]==0
    assert (H/'state/home-summary.json').read_bytes()==doc
finally:
    (E/'wide-results.json').write_text(json.dumps(results,indent=2)); shutil.rmtree(T)
