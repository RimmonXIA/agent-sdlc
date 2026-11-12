#!/usr/bin/env python3
"""Manual analysis-only impact check; model output needs semantic review."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from run_codex_checks import git, write, tracked_state, commands_from_events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch-dir', type=Path, required=True)
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    args.scratch_dir.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='impact-baseline-' if args.baseline else 'impact-', dir=args.scratch_dir))
    repo = root/'independent-repo'
    repo.mkdir()
    git(repo, 'init', '-b', 'main')
    fixtures = {
        'AGENTS.md': '# Rules\nAnalysis requests must leave the working tree unchanged. No staging or commits unless requested.\n',
        'README.md': '# Batch scheduler\nPublic v2 job records use integer `delay` in seconds. A separate legacy v1 serializer must keep seconds until its retirement. External v2 consumers are maintained elsewhere; their inventory is unavailable here.\n',
        'scheduler.py': 'def job(delay):\n    return {"delay": delay}\n',
        'transport.py': 'import json\nfrom scheduler import job as make_record\n\ndef encode(wait):\n    return json.dumps(make_record(wait))\n',
        'dashboard.py': 'import json\n\ndef remaining_minutes(payload):\n    record = json.loads(payload)\n    return record["delay"] / 60\n',
        'legacy.py': 'def serialize_v1(delay_seconds):\n    return {"delay": delay_seconds}\n',
        'fixtures/pending.json': '{"delay": 120}\n',
        'replay.py': 'import json\nfrom transport import encode\n\ndef replay(path):\n    return encode(json.loads(path.read_text())["delay"])\n',
        'config/defaults.json': '{"wait": 120}\n',
        'worker.py': 'import json\nfrom transport import encode\n\ndef submit(config):\n    return encode(config["wait"])\n',
        'tests/test_transport.py': 'import unittest\nfrom transport import encode\nclass EncodingTests(unittest.TestCase):\n    def test_delay(self):\n        self.assertEqual(encode(120), \'{"delay": 120}\')\n',
        'docs/api.md': '# v2 records\n`delay` is an integer number of seconds. Persisted records have no schema version.\n',
        'docs/history.md': '# Past release\nv1 added the delay field in seconds. This page records the historical release.\n',
        'ui/animation.py': 'delay = 120  # animation frames; unrelated to scheduling\n',
        'WORK.md': '# Active work\n- [ ] Add a dashboard alert when remaining_minutes is under one minute.\n',
        'notes.txt': 'Existing personal work.\n',
    }
    for name, body in fixtures.items():
        write(repo, name, body)
    git(repo, 'add', '.')
    git(repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Define scheduler contract and consumers')
    write(repo, 'notes.txt', 'UNRELATED USER EDIT: preserve exactly.\n')
    before, head = tracked_state(repo), git(repo, 'rev-parse', 'HEAD')
    prompt = 'Analyze the impact of changing the public v2 job delay field from integer seconds to integer milliseconds, keeping its field name and integer type. Identify the necessary handling scope and unresolved questions. Analysis only: do not modify files, stage, or commit.'
    if not args.baseline:
        prompt = 'Use $change-impact. '+prompt
    command = ['codex', 'exec', '--ephemeral', '--json', '-C', str(repo), '-s', 'workspace-write', '-c', 'approval_policy="never"', '-o', str(root/'answer.txt')]
    if args.baseline:
        skill = Path.home()/'.agents/skills/change-impact/SKILL.md'
        command += ['-c', 'skills.config=[{path='+json.dumps(str(skill))+',enabled=false}]']
    command.append(prompt)
    (root/'invocation.json').write_text(json.dumps({'prompt': prompt, 'baseline': args.baseline, 'configuration': 'normal user configuration; no parent session or model override'}, indent=2)+'\n')
    print(json.dumps({'state': 'running', 'artifact_dir': str(root)}), flush=True)
    try:
        with (root/'events.jsonl').open('w') as out, (root/'stderr.txt').open('w') as err:
            code = subprocess.run(command, stdout=out, stderr=err, timeout=240).returncode
    except subprocess.TimeoutExpired:
        code = 'timeout'
    commands, usage = commands_from_events(root/'events.jsonl')
    result = {'baseline': args.baseline, 'artifact_dir': str(root), 'exit_code': code,
              'skill_read_observed': any('change-impact' in c and 'SKILL.md' in c for c in commands),
              'files_unchanged': before == tracked_state(repo),
              'no_staging': not git(repo, 'diff', '--cached', '--name-only'),
              'no_new_commit': head == git(repo, 'rev-parse', 'HEAD'), 'usage': usage}
    (root/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)
    return 0 if code == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
