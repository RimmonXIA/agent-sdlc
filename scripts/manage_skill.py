#!/usr/bin/env python3
"""Install a self-contained skill; never overwrite unowned or locally edited data."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import zipfile

NAME = 'repo-continuity'
SKILL_NAMES = ('repo-continuity', 'change-closeout', 'change-impact')
RECEIPT = '.agent-sdlc-install.json'
ROOT = Path(__file__).resolve().parent.parent


class LifecycleError(Exception):
    pass


def digest_files(root):
    if root.is_symlink() or not root.is_dir():
        raise LifecycleError('Skill path must be a real directory, not a symlink.')
    files = {}
    for item in sorted(root.rglob('*')):
        if item.is_symlink():
            raise LifecycleError('Symlinks in a managed skill are not supported.')
        if item.is_dir():
            continue
        if not item.is_file():
            raise LifecycleError('Only regular skill files are supported.')
        name = item.relative_to(root).as_posix()
        if name != RECEIPT:
            files[name] = hashlib.sha256(item.read_bytes()).hexdigest()
    return files


def source_files(source, skill_name=NAME):
    files = digest_files(source)
    if (source / RECEIPT).exists():
        raise LifecycleError('Distribution source must not contain an install receipt.')
    if 'SKILL.md' not in files:
        raise LifecycleError('Distribution is missing SKILL.md.')
    body = (source / 'SKILL.md').read_text(encoding='utf-8')
    if skill_name not in SKILL_NAMES or not re.search(r'^name: '+re.escape(skill_name)+r'$', body, re.M):
        raise LifecycleError('Distribution skill name does not match the selected skill.')
    for name in files:
        if not name.endswith('.md'):
            continue
        page = source / name
        for link in re.findall(r'\]\(([^)]+)\)', page.read_text(encoding='utf-8')):
            if link.startswith(('https://', 'http://', '#')):
                continue
            reference = (page.parent / link.split('#', 1)[0]).resolve()
            try:
                reference.relative_to(source.resolve())
            except ValueError:
                raise LifecycleError('Skill reference escapes the distribution.')
            if not reference.is_file():
                raise LifecycleError('Distribution has a missing local reference.')
    return files


def owned_files(target, skill_name=NAME):
    actual = digest_files(target)
    path = target / RECEIPT
    try:
        receipt = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise LifecycleError('Existing skill has no valid ownership receipt; refusing changes.')
    if not isinstance(receipt, dict) or receipt.get('owner') != 'agent-sdlc/'+skill_name:
        raise LifecycleError('Existing skill is not owned by this installer.')
    recorded = receipt.get('files')
    if not isinstance(recorded, dict) or actual != recorded:
        raise LifecycleError('Managed skill has local changes; preserve or reconcile them first.')
    return actual


@contextmanager
def operation_lock(directory, skill_name=NAME):
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / f'.{skill_name}.lock'
    try:
        lock.mkdir()
    except FileExistsError:
        raise LifecycleError('Another lifecycle operation may be active; inspect the lock before retrying.')
    try:
        yield
    finally:
        lock.rmdir()


def install(source, directory, skill_name=NAME):
    wanted = source_files(source, skill_name)
    target = directory / skill_name
    # Resolve containment before any mutation; never move the distribution itself.
    src, dst = source.resolve(), target.resolve()
    if src == dst or src in dst.parents or dst in src.parents:
        raise LifecycleError('Source and installation must not overlap.')
    with operation_lock(directory, skill_name):
        exists = target.exists() or target.is_symlink()
        if exists and owned_files(target, skill_name) == wanted:
            return {'status': 'unchanged', 'path': str(target)}
        stage = Path(tempfile.mkdtemp(prefix=f'.{skill_name}-transaction-', dir=directory.parent))
        new, old = stage / 'new', stage / 'old'
        preserve_backup = False
        try:
            shutil.copytree(source, new, symlinks=False)
            if digest_files(new) != wanted:
                raise LifecycleError('Source changed during staging; retry with a stable distribution.')
            (new / RECEIPT).write_text(json.dumps({'owner': 'agent-sdlc/'+skill_name, 'files': wanted}, indent=2) + '\n', encoding='utf-8')
            if exists:
                owned_files(target, skill_name)
                os.replace(target, old)
            try:
                os.replace(new, target)
            except BaseException:
                if exists:
                    try:
                        os.replace(old, target)
                    except BaseException as restore_error:
                        preserve_backup = True
                        raise LifecycleError(f'Restore failed; previous installation preserved at {old}') from restore_error
                raise
        finally:
            if not preserve_backup:
                shutil.rmtree(stage)
        return {'status': 'updated' if exists else 'installed', 'path': str(target)}


def status(directory, skill_name=NAME):
    target = directory / skill_name
    if not target.exists() and not target.is_symlink():
        return {'status': 'absent', 'path': str(target)}
    files = owned_files(target, skill_name)
    return {'status': 'installed', 'path': str(target), 'files': len(files)}


def uninstall(directory, skill_name=NAME):
    target = directory / skill_name
    if not target.exists() and not target.is_symlink():
        return {'status': 'absent', 'path': str(target)}
    with operation_lock(directory, skill_name):
        owned_files(target, skill_name)
        with tempfile.TemporaryDirectory(prefix=f'.{skill_name}-transaction-', dir=directory.parent) as stage:
            os.replace(target, Path(stage) / 'removed')
    return {'status': 'removed', 'path': str(target)}


def bundle(output, skill_name=NAME):
    source = ROOT / 'skills' / skill_name
    source_files(source, skill_name)
    selected = [ROOT / 'USAGE.md', ROOT / 'scripts' / 'manage_skill.py']
    selected += [p for p in source.rglob('*') if p.is_file()]
    output = output.absolute()
    if output in selected:
        raise LifecycleError('Bundle output cannot overwrite a distribution file.')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Stable archive metadata makes distribution checks independent of file mtimes.
    with tempfile.NamedTemporaryFile(prefix='.bundle-', suffix='.zip', dir=output.parent, delete=False) as staged:
        staged_path = Path(staged.name)
    try:
        with zipfile.ZipFile(staged_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for item in sorted(selected):
                info = zipfile.ZipInfo(item.relative_to(ROOT).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, item.read_bytes())
        os.replace(staged_path, output)
    finally:
        staged_path.unlink(missing_ok=True)
    return {'status': 'bundled', 'path': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    default = Path.home() / '.agents' / 'skills'
    for command in ('install', 'status', 'uninstall'):
        child = sub.add_parser(command)
        child.add_argument('--skill', choices=SKILL_NAMES, default=NAME)
        child.add_argument('--skills-dir', type=Path, default=default)
        if command == 'install':
            child.add_argument('--source', type=Path)
    child = sub.add_parser('bundle')
    child.add_argument('--skill', choices=SKILL_NAMES, default=NAME)
    child.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'install':
            result = install(args.source or ROOT / 'skills' / args.skill, args.skills_dir.absolute(), args.skill)
        elif args.command == 'status':
            result = status(args.skills_dir.absolute(), args.skill)
        elif args.command == 'uninstall':
            result = uninstall(args.skills_dir.absolute(), args.skill)
        else:
            result = bundle(args.output, args.skill)
    except (LifecycleError, OSError) as error:
        # Never dump environment, credentials, or subprocess output on failure.
        print(json.dumps({'status': 'error', 'reason': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
