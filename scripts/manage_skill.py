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
OWNER = 'agent-sdlc/repo-continuity'
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


def source_files(source):
    files = digest_files(source)
    if (source / RECEIPT).exists():
        raise LifecycleError('Distribution source must not contain an install receipt.')
    if 'SKILL.md' not in files:
        raise LifecycleError('Distribution is missing SKILL.md.')
    body = (source / 'SKILL.md').read_text(encoding='utf-8')
    if not re.search(r'^name: repo-continuity$', body, re.M):
        raise LifecycleError('Distribution skill name does not match repo-continuity.')
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


def owned_files(target):
    actual = digest_files(target)
    path = target / RECEIPT
    try:
        receipt = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise LifecycleError('Existing skill has no valid ownership receipt; refusing changes.')
    if not isinstance(receipt, dict) or receipt.get('owner') != OWNER:
        raise LifecycleError('Existing skill is not owned by this installer.')
    recorded = receipt.get('files')
    if not isinstance(recorded, dict) or actual != recorded:
        raise LifecycleError('Managed skill has local changes; preserve or reconcile them first.')
    return actual


@contextmanager
def operation_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / f'.{NAME}.lock'
    try:
        lock.mkdir()
    except FileExistsError:
        raise LifecycleError('Another lifecycle operation may be active; inspect the lock before retrying.')
    try:
        yield
    finally:
        lock.rmdir()


def install(source, directory):
    wanted = source_files(source)
    target = directory / NAME
    # Resolve containment before any mutation; never move the distribution itself.
    src, dst = source.resolve(), target.resolve()
    if src == dst or src in dst.parents or dst in src.parents:
        raise LifecycleError('Source and installation must not overlap.')
    with operation_lock(directory):
        exists = target.exists() or target.is_symlink()
        if exists and owned_files(target) == wanted:
            return {'status': 'unchanged', 'path': str(target)}
        stage = Path(tempfile.mkdtemp(prefix=f'.{NAME}-transaction-', dir=directory.parent))
        new, old = stage / 'new', stage / 'old'
        preserve_backup = False
        try:
            shutil.copytree(source, new, symlinks=False)
            if digest_files(new) != wanted:
                raise LifecycleError('Source changed during staging; retry with a stable distribution.')
            (new / RECEIPT).write_text(json.dumps({'owner': OWNER, 'files': wanted}, indent=2) + '\n', encoding='utf-8')
            if exists:
                owned_files(target)
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


def status(directory):
    target = directory / NAME
    if not target.exists() and not target.is_symlink():
        return {'status': 'absent', 'path': str(target)}
    files = owned_files(target)
    return {'status': 'installed', 'path': str(target), 'files': len(files)}


def uninstall(directory):
    target = directory / NAME
    if not target.exists() and not target.is_symlink():
        return {'status': 'absent', 'path': str(target)}
    with operation_lock(directory):
        owned_files(target)
        with tempfile.TemporaryDirectory(prefix=f'.{NAME}-transaction-', dir=directory.parent) as stage:
            os.replace(target, Path(stage) / 'removed')
    return {'status': 'removed', 'path': str(target)}


def bundle(output):
    source = ROOT / 'skills' / NAME
    source_files(source)
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
        child.add_argument('--skills-dir', type=Path, default=default)
        if command == 'install':
            child.add_argument('--source', type=Path, default=ROOT / 'skills' / NAME)
    child = sub.add_parser('bundle')
    child.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'install':
            result = install(args.source, args.skills_dir.absolute())
        elif args.command == 'status':
            result = status(args.skills_dir.absolute())
        elif args.command == 'uninstall':
            result = uninstall(args.skills_dir.absolute())
        else:
            result = bundle(args.output)
    except (LifecycleError, OSError) as error:
        # Never dump environment, credentials, or subprocess output on failure.
        print(json.dumps({'status': 'error', 'reason': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
