#!/usr/bin/env python3
"""Run bounded fresh-session checks in synthetic, independent repositories.

Invokes the installed Codex CLI using its normal model/auth configuration.
This is manual integration checking, not part of unittest discovery.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

SKILL_PATH = Path.home() / '.agents' / 'skills' / 'repo-continuity' / 'SKILL.md'


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def write(root, name, body):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding='utf-8')


def setup_resume(root):
    git(root, 'init', '-b', 'main')
    write(root, 'README.md', '# Report size labels\n\nCurrent work is tracked in TASKS.md; the active contract is docs/size.md.\n')
    write(root, 'labels.py', 'def render_size(value):\n    return f"{value} bytes"\n')
    write(root, 'TASKS.md', '# Tasks\n\n- Use decimal KB labels for large sizes.\n')
    write(root, 'notes/editor.txt', 'Existing unrelated editorial draft.\n')
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Initial decimal-label proposal')
    write(root, 'AGENTS.md', '# Project rules\n\nRun `python3 -m unittest discover -s tests`. Do not edit the tests. Do not create commits. Preserve unrelated work.\n')
    write(root, 'TASKS.md', '# Active work\n\n- Finish render_size migration according to docs/size.md. The decimal KB proposal was rejected. Only labels.py needs behavior changes.\n')
    write(root, 'docs/size.md', '# Size contract\n\nInput is an integer byte count. Negative values raise ValueError. Values below 1024 render as `N B`; values of at least 1024 render as one decimal place in KiB using 1024 bytes per KiB. Input remains bytes, never KiB.\n')
    write(root, 'tests/test_labels.py', '''import unittest
from labels import render_size
class SizeTests(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(render_size(0), '0 B')
        self.assertEqual(render_size(1023), '1023 B')
    def test_binary_units(self):
        self.assertEqual(render_size(1024), '1.0 KiB')
        self.assertEqual(render_size(1536), '1.5 KiB')
        self.assertEqual(render_size(2048), '2.0 KiB')
    def test_negative(self):
        with self.assertRaises(ValueError):
            render_size(-1)
''')
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Adopt binary byte contract; implementation remains unfinished')
    write(root, 'notes/editor.txt', 'UNRELATED USER EDIT: keep this exact text.\n')


def setup_queue(root):
    git(root, 'init', '-b', 'main')
    write(root, 'README.md', '# Pending jobs\n\nThe active work is in work/current.toml. Its contract is docs/queue.md.\n')
    write(root, 'AGENTS.md', '# Project rules\n\nRun `python3 -m unittest discover -s tests`. Do not edit tests or make commits. Preserve unrelated edits.\n')
    write(root, 'queueing.py', 'def pending_ids(values):\n    return list(values)\n')
    write(root, 'work/current.toml', '[active]\nid = "deduplicate"\nstate = "open"\ngoal = "Complete pending_ids according to docs/queue.md"\n\n[next]\nid = "persist"\nstate = "open"\ngoal = "Evaluate durable persistence later; not part of the active task"\n')
    write(root, 'docs/queue.md', '# Queue contract\n\nGiven a list of job-ID strings, pending_ids returns each identifier once in original first-seen order. It must not modify the input list. Persistence is outside this task.\n')
    write(root, 'tests/test_queue.py', """import unittest
from queueing import pending_ids
class QueueTests(unittest.TestCase):
    def test_first_seen(self):
        self.assertEqual(pending_ids(['b','a','b','c','a']), ['b','a','c'])
    def test_input_unchanged(self):
        values=['x','x','y']
        self.assertEqual(pending_ids(values), ['x','y'])
        self.assertEqual(values, ['x','x','y'])
    def test_empty(self):
        self.assertEqual(pending_ids([]), [])
""")
    write(root, 'notes/editor.txt', 'Existing unrelated editorial draft.\n')
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Define the active queue task and leave persistence for later')
    write(root, 'notes/editor.txt', 'UNRELATED USER EDIT: keep this exact text.\n')


def tracked_state(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}


def commands_from_events(path):
    commands = []
    usage = {}
    for line in path.read_text(errors='replace').splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        item = event.get('item', {})
        if item.get('type') == 'command_execution' and event.get('type') == 'item.completed':
            commands.append(item.get('command', ''))
        if event.get('type') == 'turn.completed':
            usage = event.get('usage', {})
    return commands, usage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', choices=('explicit', 'implicit', 'baseline', 'negative', 'no-task', 'queue', 'queue-baseline'))
    parser.add_argument('--scratch-dir', type=Path, required=True)
    args = parser.parse_args()
    args.scratch_dir.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=args.case+'-', dir=args.scratch_dir))
    repo = root / 'independent-repo'
    repo.mkdir()
    resume = args.case in ('explicit', 'implicit', 'baseline', 'queue', 'queue-baseline')
    queue = args.case in ('queue', 'queue-baseline')
    if resume:
        (setup_queue if queue else setup_resume)(repo)
        before_head = git(repo, 'rev-parse', 'HEAD')
    else:
        write(repo, 'README.md', '# Notes\n\nNo active task has been specified here.\n')
    before = tracked_state(repo)
    prompts = {
        'explicit': 'Use $repo-continuity to pick up the unfinished formatting migration and finish the active task in this repository.',
        'implicit': '接手这个项目，继续完成现在还没做完的迁移工作。',
        'baseline': '接手这个项目，继续完成现在还没做完的迁移工作。',
        'queue': '接手这个项目，继续完成当前任务。',
        'queue-baseline': '接手这个项目，继续完成当前任务。',
        'negative': 'Calculate 17 times 23. Do not modify any files.',
        'no-task': 'Use $repo-continuity to identify what work should be resumed here. Only analyze; do not modify files. If the current task cannot be determined, ask what you need rather than inventing one.',
    }
    command = ['codex', 'exec', '--ephemeral', '--json', '-C', str(repo), '-s', 'workspace-write', '-c', 'approval_policy="never"', '--skip-git-repo-check', '-o', str(root/'answer.txt')]
    if args.case in ('baseline', 'queue-baseline'):
        command += ['-c', 'skills.config=[{path='+json.dumps(str(SKILL_PATH))+',enabled=false}]']
    command.append(prompts[args.case])
    (root/'invocation.json').write_text(json.dumps({'case':args.case,'cwd':str(repo),'prompt':prompts[args.case],'configuration':'normal user configuration; no parent conversation; no model override','skill_disabled':args.case in ('baseline','queue-baseline')},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'state':'running','case':args.case,'artifact_dir':str(root)}), flush=True)
    try:
        with (root/'events.jsonl').open('w') as stdout, (root/'stderr.txt').open('w') as stderr:
            result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=240)
        code = result.returncode
    except subprocess.TimeoutExpired:
        code = 'timeout'
    commands, usage = commands_from_events(root/'events.jsonl')
    after = tracked_state(repo)
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k)!=after.get(k))
    loaded = any('repo-continuity' in c and ('SKILL.md' in c or '/repo-continuity/' in c) for c in commands)
    summary = {'case':args.case,'exit_code':code,'artifact_dir':str(root),'skill_read_observed':loaded,'changed_files':changed,'tool_command_count':len(commands),'usage':usage}
    if resume:
        check = subprocess.run([sys.executable,'-m','unittest','discover','-s','tests'],cwd=repo,text=True,capture_output=True)
        summary['contract_tests_pass']=check.returncode==0
        summary['unrelated_preserved']=before['notes/editor.txt']==after.get('notes/editor.txt')
        test_path = 'tests/test_queue.py' if queue else 'tests/test_labels.py'
        summary['tests_preserved']=before[test_path]==after.get(test_path)
        summary['no_new_commit']=git(repo,'rev-parse','HEAD')==before_head
        allowed = ('queueing.py','work/current.toml') if queue else ('labels.py','TASKS.md')
        summary['task_artifacts_only']=all(k in allowed for k in changed)
        if queue:
            import tomllib
            task = tomllib.loads((repo/'work/current.toml').read_text())
            summary['active_task_closed']=task['active']['state'] in ('done','complete','completed','closed')
            summary['future_task_preserved']=task['next']['state']=='open' and task['next']['id']=='persist'
    else:
        summary['no_writes']=before==after
    (root/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False), flush=True)
    # Raw process output stays in scratch; don't dump user configuration or error logs.
    return 0 if code==0 else 1


if __name__=='__main__':
    raise SystemExit(main())
