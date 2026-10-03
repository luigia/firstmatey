import os, pathlib, tempfile, shutil, subprocess, json, hashlib, base64
ROOT = pathlib.Path.cwd()
EVIDENCE = pathlib.Path('/Users/luigi/.no-mistakes/evidence/01M40DW0SN0B03C3NZ8A1816YJ')
lab = pathlib.Path(tempfile.mkdtemp(prefix='.key-order-live-', dir=ROOT))
log = []
def note(s):
    print(s, flush=True)
    log.append(s)
def run(cli, home, seed, mode='--secondmate-home-summary'):
    env = {k:v for k,v in os.environ.items() if not (k.startswith('FM_') or k in ('PERL_HASH_SEED', 'PERL_PERTURB_KEYS'))}
    env.update(FM_HOME=str(home), FM_ROOT_OVERRIDE=str(ROOT), FM_SNAPSHOT_NOW='2026-07-25T00:00:00Z', FM_SNAPSHOT_NOW_EPOCH='1784937600', PERL_HASH_SEED=str(seed), PERL_PERTURB_KEYS='2')
    return subprocess.run([str(cli), mode], env=env, check=True, capture_output=True).stdout
try:
    home = lab/'home'
    for d in ('state','data','projects','config'):
        (home/d).mkdir(parents=True)
    landed = '## In flight\n\n## Queued\n\n## Done\n- [x] shipped - Shipped https://github.com/kunchenguid/firstmate/pull/9 (repo: alpha) (kind: ship) (merged 2026-07-06)\n'
    (home/'data/backlog.md').write_text(landed)
    cli = ROOT/'bin/fm-fleet-snapshot.sh'
    outputs = [run(cli, home, seed) for seed in range(1,17)]
    for output in outputs:
        doc = json.loads(output)
        assert doc['valid'] is True
        assert doc['landed'][0]['completion'] == {'date':'2026-07-06','verb':'merged'}
    assert len(set(outputs)) == 1
    (EVIDENCE/'landed-home-summary.json').write_bytes(outputs[0])
    note('LIVE: bin/fm-fleet-snapshot.sh --secondmate-home-summary: 16 independent Perl seeds, exact raw stdout bytes identical; landed completion date=2026-07-06, verb=merged; valid=true.')
    note('Published summary SHA256: '+hashlib.sha256(outputs[0]).hexdigest())
    baseline = lab/'baseline-bin'
    shutil.copytree(ROOT/'bin', baseline)
    old = subprocess.run(['git','show','e31bc6e620ca532c2e0e0b72f3fd7c0869a12270:bin/fm-hold-reason-lib.sh'], check=True, capture_output=True).stdout
    (baseline/'fm-hold-reason-lib.sh').write_bytes(old)
    before = [run(baseline/'fm-fleet-snapshot.sh', home, seed) for seed in range(1,17)]
    distinct = len(set(before))
    assert distinct > 1, 'baseline regression did not reproduce'
    for n, output in enumerate(before):
        if output != before[0]:
            (EVIDENCE/'baseline-summary-a.json').write_bytes(before[0])
            (EVIDENCE/'baseline-summary-b.json').write_bytes(output)
            break
    note(f'BASELINE: same CLI and home, pre-fix decoder: {distinct} distinct raw stdout byte sequences across 16 seeds. Regression reproduced.')
    reason = 'Choose (API), "quoted" café 船\nsecond line'
    encoded = 'fm-hold-v1:'+base64.b64encode(reason.encode()).decode()
    malformed = 'fm-hold-v1:not-base64!'
    (home/'data/backlog.md').write_text('## In flight\n\n## Queued\n'
        +f'- [ ] decision - API choice (repo: alpha) (kind: ship) (hold: {encoded}) (hold-kind: captain) (since 2026-07-24)\n'
        +f'- [ ] malformed - Historical reason (repo: alpha) (kind: ship) (hold: {malformed}) (hold-kind: captain) (since 2026-07-24)\n\n'
        +landed.split('## Done')[1].join(['## Done','']))
    held = [run(cli, home, seed) for seed in range(1,17)]
    assert len(set(held)) == 1
    for output in held:
        doc = json.loads(output)
        assert doc['valid'] is True
        assert doc['state'] == 'captain_decision'
        queued = {r['id']:r for r in doc['queued']}
        assert queued['decision']['hold_reason'] == ' '.join(reason.split())
        assert queued['malformed']['hold_reason'] == malformed
        assert doc['landed'][0]['completion'] == {'date':'2026-07-06','verb':'merged'}
    (EVIDENCE/'held-home-summary.json').write_bytes(held[0])
    snapshot = run(cli, home, 7, '--json')
    doc = json.loads(snapshot)
    records = {r['id']:r for r in doc['backlog']['records']}
    assert records['decision']['hold_reason'] == reason
    assert records['malformed']['hold_reason'] == malformed
    (EVIDENCE/'held-fleet-snapshot.json').write_bytes(snapshot)
    note('LIVE: isolated home with encoded Unicode, parentheses, commas, quotes and newline plus malformed base64 hold: 16 seeds produce identical raw summary bytes; decoded reason preserved with documented summary whitespace normalization, malformed reason unchanged; captain_decision and landed completion retained. --json also preserves both reasons.')
finally:
    shutil.rmtree(lab)
    (EVIDENCE/'key-order-validation.log').write_text('\n'.join(log)+'\n')
