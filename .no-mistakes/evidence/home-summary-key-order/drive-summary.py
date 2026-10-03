#!/usr/bin/env python3
"""Drive the real summary publisher in a disposable worktree-local home, no stubs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

root = Path.cwd()
evidence = Path('/Users/luigi/.no-mistakes/evidence/01M40X55R4W1PVBEV3HNFZBJ5B')
scratch = root / '.test-summary-live'
home = scratch / 'home'
for name in ('state', 'data', 'config', 'projects'):
    (home / name).mkdir(parents=True, exist_ok=True)
env = dict(os.environ)
for key in ('FM_ROOT_OVERRIDE', 'FM_STATE_OVERRIDE', 'FM_DATA_OVERRIDE', 'FM_CONFIG_OVERRIDE', 'FM_PROJECTS_OVERRIDE', 'FM_GATE_REFUSE_BYPASS', 'FM_TEST_SEAM'):
    env.pop(key, None)
env.update(FM_HOME=str(home), FM_ROOT_OVERRIDE=str(root), TMPDIR=str(scratch / 'tmp'), FM_SNAPSHOT_NOW='2026-07-25T00:00:00Z', PERL_PERTURB_KEYS='2')
reason = 'Choose (blue), "green" — café\nsecond line'
encoded = subprocess.check_output(['/bin/bash', '-c', '. bin/fm-hold-reason-lib.sh; fm_hold_reason_encode "$1"', 'encode', reason], env=env, text=True)
(home / 'data' / 'backlog.md').write_text(f'''## In flight

## Queued
- [ ] encoded-call - Choose route (repo: alpha) (kind: captain) (since 2026-07-24) (hold: {encoded}) (hold-kind: captain)
- [ ] plain-call - Plain route (repo: alpha) (kind: captain) (since 2026-07-24) (hold: literal reason) (hold-kind: captain)
- [ ] malformed-call - Malformed marker (repo: alpha) (kind: captain) (since 2026-07-24) (hold: fm-hold-v1:%%%) (hold-kind: captain)
- [ ] invalid-utf8-call - Invalid UTF-8 marker (repo: alpha) (kind: captain) (since 2026-07-24) (hold: fm-hold-v1:/w==) (hold-kind: captain)

## Done
- [x] shipped - Shipped https://github.com/kunchenguid/firstmate/pull/9 (repo: alpha) (kind: ship) (merged 2026-07-06)
''')

def run(command, seed):
    local = dict(env, PERL_HASH_SEED=str(seed))
    result = subprocess.run(command, env=local, capture_output=True, check=True)
    if result.stderr:
        raise AssertionError(result.stderr.decode())
    return result.stdout

baseline = scratch / 'baseline'
shutil.copytree(root / 'bin', baseline / 'bin', dirs_exist_ok=True)
old = subprocess.check_output(['git', 'show', '1f3e769616fdf9f31f85f4c3e6a9f71606634238:bin/fm-hold-reason-lib.sh'])
(baseline / 'bin' / 'fm-hold-reason-lib.sh').write_bytes(old)
log = []
outputs = {}
for label, publisher in [('pre-fix decoder', baseline / 'bin' / 'fm-home-summary-refresh.sh'), ('fixed product', root / 'bin' / 'fm-home-summary-refresh.sh')]:
    emitted = []
    for seed in range(1, 17):
        run([str(publisher)], seed)
        data = (home / 'state' / 'home-summary.json').read_bytes()
        summary = json.loads(data)
        assert summary['valid'] is True and summary['state'] == 'captain_decision'
        assert summary['landed'][0]['completion'] == {'date': '2026-07-06', 'verb': 'merged'}
        queued = {row['id']: row['hold_reason'] for row in summary['queued']}
        assert queued == {'encoded-call': 'Choose (blue), "green" — café second line', 'plain-call': 'literal reason', 'malformed-call': 'fm-hold-v1:%%%', 'invalid-utf8-call': 'fm-hold-v1:/w=='}
        assert summary['counts']['decisions_open'] == 4 and summary['counts']['landed'] == 1
        emitted.append(data)
        log.append(f'{label}: PERL_HASH_SEED={seed} PERL_PERTURB_KEYS=2 FM_HOME=<isolated home> {publisher.relative_to(root)} -> state/home-summary.json sha256={hashlib.sha256(data).hexdigest()}')
    outputs[label] = emitted
    log.append(f'{label}: {len(set(emitted))} distinct published byte sequences for unchanged state')
assert len(set(outputs['pre-fix decoder'])) > 1, 'baseline did not reproduce the bug'
assert len(set(outputs['fixed product'])) == 1, 'fixed publisher changed bytes'
assert all(json.loads(data) == json.loads(outputs['fixed product'][0]) for data in outputs['pre-fix decoder']), 'semantic data changed across decoder versions'
snapshot = run([str(root / 'bin' / 'fm-fleet-snapshot.sh'), '--secondmate-home-summary'], 99)
assert snapshot == outputs['fixed product'][0], 'publisher does not preserve snapshot bytes'
log.append('PERL_HASH_SEED=99 bin/fm-fleet-snapshot.sh --secondmate-home-summary: exact byte match with published ledger')
# Inspect the full public snapshot too: unlike the home projection, it preserves newlines.
full = json.loads(run([str(root / 'bin' / 'fm-fleet-snapshot.sh'), '--json'], 99))
reasons = {row['id']: row['hold_reason'] for row in full['backlog']['records'] if row.get('hold_reason') is not None}
assert reasons['encoded-call'] == reason
assert reasons['malformed-call'] == 'fm-hold-v1:%%%'
assert reasons['invalid-utf8-call'] == 'fm-hold-v1:/w=='
assert reasons['plain-call'] == 'literal reason'
log.append('bin/fm-fleet-snapshot.sh --json: decoded Unicode, parentheses, quotes, comma, and newline retained; plain and malformed markers unchanged')
(evidence / 'published-home-summary.json').write_bytes(outputs['fixed product'][0])
(evidence / 'snapshot-backlog.json').write_text(json.dumps(full['backlog'], ensure_ascii=False, indent=2) + '\n')
(evidence / 'publication-transcript.txt').write_text('\n'.join(log) + '\n\nActual published product output:\n' + outputs['fixed product'][0].decode())
print('\n'.join(log))
