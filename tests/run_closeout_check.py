#!/usr/bin/env python3
"""Manually check closeout behavior in a fresh synthetic repository/session."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from run_codex_checks import git, write, tracked_state, commands_from_events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch-dir', type=Path, required=True)
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    args.scratch_dir.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='closeout-baseline-' if args.baseline else 'closeout-', dir=args.scratch_dir))
    repo = root / 'independent-repo'
    repo.mkdir()
    git(repo, 'init', '-b', 'main')
    write(repo, 'README.md', '# Request worker\n\nWORK.md tracks the active change. docs/api.md is the current API description. defaults.env mirrors factory defaults, not production overrides.\n')
    write(repo, 'AGENTS.md', '# Local rules\n\nUse Python standard library tests: `python3 -m unittest discover -s tests`. Preserve unrelated edits and existing tests. Never stage or commit unless asked.\n')
    write(repo, 'worker.py', 'DEFAULT_TIMEOUT_SECONDS = 10\n\ndef request_timeout():\n    return DEFAULT_TIMEOUT_SECONDS\n')
    write(repo, 'tests/test_worker.py', 'import unittest\nfrom worker import request_timeout\nclass WorkerTests(unittest.TestCase):\n    def test_factory_default(self):\n        self.assertEqual(request_timeout(), 10)\n')
    write(repo, 'docs/api.md', '# Requests\n\nThe default timeout is 10 seconds. All timeout inputs remain seconds.\n\nRetries reuse request_id because workers may replay the same request; this is necessary for idempotency.\n')
    write(repo, 'docs/release-notes.md', '# Release and migration history\n\nThe legacy endpoint remains supported until 2027-04-01. This compatibility commitment is unchanged by timeout work.\n')
    write(repo, 'defaults.env', '# Factory defaults\nTIMEOUT_SECONDS=10\n')
    write(repo, 'WORK.md', '# Work\n\n- [ ] TIMEOUT_DEFAULT: raise the factory default from 10 to 30 seconds to allow worker cold starts; units and retry behavior remain unchanged.\n- [ ] FUTURE_RETRY: evaluate alternative retry policies later; outside this change.\n')
    write(repo, 'notes.txt', 'Existing unrelated notes.\n')
    git(repo, 'add', '.')
    git(repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Define request timeout and existing compatibility commitment')
    write(repo, 'worker.py', 'DEFAULT_TIMEOUT_SECONDS = 30\n\ndef request_timeout():\n    return DEFAULT_TIMEOUT_SECONDS\n')
    write(repo, 'tests/test_worker.py', 'import unittest\nfrom worker import request_timeout\nclass WorkerTests(unittest.TestCase):\n    def test_factory_default(self):\n        self.assertEqual(request_timeout(), 30)\n')
    with (repo/'docs/api.md').open('a') as page:
        page.write('\n## Implementation update\n\nThis session changed the default from 10 to 30 seconds. The edit has been completed and tests were run.\n')
    write(repo, 'notes.txt', 'UNRELATED USER EDIT: keep this exact text.\n')
    before, head = tracked_state(repo), git(repo, 'rev-parse', 'HEAD')
    prompt = 'Finish this default-timeout change and prepare it for handoff. Do not stage or commit.'
    if not args.baseline:
        prompt = 'Use $change-closeout. '+prompt
    command = ['codex','exec','--ephemeral','--json','-C',str(repo),'-s','workspace-write','-c','approval_policy="never"','-o',str(root/'answer.txt')]
    if args.baseline:
        path = Path.home()/'.agents'/'skills'/'change-closeout'/'SKILL.md'
        command += ['-c','skills.config=[{path='+json.dumps(str(path))+',enabled=false}]']
    command.append(prompt)
    (root/'invocation.json').write_text(json.dumps({'prompt':prompt,'baseline':args.baseline,'configuration':'normal user configuration; no parent conversation; no model override'},indent=2)+'\n')
    print(json.dumps({'state':'running','artifact_dir':str(root)}),flush=True)
    try:
        with (root/'events.jsonl').open('w') as stdout, (root/'stderr.txt').open('w') as stderr:
            code = subprocess.run(command,stdout=stdout,stderr=stderr,timeout=240).returncode
    except subprocess.TimeoutExpired:
        code = 'timeout'
    commands, usage = commands_from_events(root/'events.jsonl')
    after = tracked_state(repo)
    tests = subprocess.run([sys.executable,'-m','unittest','discover','-s','tests'],cwd=repo,capture_output=True,text=True)
    task = (repo/'WORK.md').read_text()
    result = {
        'baseline':args.baseline,'artifact_dir':str(root),'exit_code':code,
        'skill_read_observed':any('change-closeout' in c and 'SKILL.md' in c for c in commands),
        'changed_files':sorted(p for p in before.keys()|after.keys() if before.get(p)!=after.get(p)),
        'tests_pass':tests.returncode==0,
        'factory_example_updated':'TIMEOUT_SECONDS=30' in (repo/'defaults.env').read_text(),
        'active_task_closed':'- [x] TIMEOUT_DEFAULT' in task or '- [X] TIMEOUT_DEFAULT' in task,
        'future_task_open':'- [ ] FUTURE_RETRY' in task,
        'history_preserved':before['docs/release-notes.md']==after.get('docs/release-notes.md'),
        'unrelated_preserved':before['notes.txt']==after.get('notes.txt'),
        'tests_preserved':before['tests/test_worker.py']==after.get('tests/test_worker.py'),
        'no_staging':not git(repo,'diff','--cached','--name-only'),
        'no_new_commit':head==git(repo,'rev-parse','HEAD'),
        'tool_command_count':len(commands),'usage':usage,
    }
    (root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    return 0 if code==0 else 1


if __name__=='__main__':
    raise SystemExit(main())
